#include "common.h"
#include <string.h>
#include "hardware/structs/usb.h"
#include "hardware/sync.h"
#include "tinyusb/dcd.h"
#include "tinyusb/tusb_types.h"
#include "powerSaving.h"
#include "cardOwner.h"
#include "sd/SdCard.h"
#include "usbHost.h"

//--------------------------------------------------------------------
// Configuration
//--------------------------------------------------------------------

#define EP0_PACKET_SIZE     64
#define EP_BULK_PACKET_SIZE 64

#define EP_MSC_OUT          0x01
#define EP_MSC_IN           0x81

// Sectors moved per USB transfer. Larger is faster but costs RAM; 8 sectors keeps
// the host's usual 4 KB requests to a single transfer each.
#define MSC_BUF_SECTORS     8
#define SD_SECTOR_SIZE      512

// Vendor and product ID.
//
// TODO: these are the pid.codes prototype IDs, which exist for exactly this situation:
// unreleased work that needs to enumerate. They must NOT ship. Before release the
// project needs either its own pid.codes allocation or a product ID reserved under the
// Raspberry Pi vendor ID. Do not invent a vendor ID.
#define USB_VENDOR_ID       0x1209
#define USB_PRODUCT_ID      0x0001

//--------------------------------------------------------------------
// Descriptors
//--------------------------------------------------------------------

// No serial number string is reported (iSerialNumber is 0). The obvious source would be
// the RP2040 flash unique ID, but reading it pauses XIP with interrupts disabled, and
// usbh_start() can run while the cartridge PIO is armed and a DS may be booting. Stalling
// flash there risks breaking DSi ntrboot, which the README documents as timing sensitive.
// Hosts mount mass storage without a serial; the cost is that two DSpicos on one machine
// are indistinguishable to the OS.
static const u8 sDeviceDescriptor[] =
{
    18,                                 // bLength
    TUSB_DESC_DEVICE,                   // bDescriptorType
    0x00, 0x02,                         // bcdUSB 2.00
    0x00,                               // bDeviceClass, per interface
    0x00,                               // bDeviceSubClass
    0x00,                               // bDeviceProtocol
    EP0_PACKET_SIZE,                    // bMaxPacketSize0
    USB_VENDOR_ID & 0xFF, USB_VENDOR_ID >> 8,
    USB_PRODUCT_ID & 0xFF, USB_PRODUCT_ID >> 8,
    0x00, 0x01,                         // bcdDevice 1.00
    1,                                  // iManufacturer
    2,                                  // iProduct
    0,                                  // iSerialNumber, see above
    1                                   // bNumConfigurations
};

#define CONFIG_TOTAL_LENGTH 32

static const u8 sConfigDescriptor[CONFIG_TOTAL_LENGTH] =
{
    // Configuration
    9,                                  // bLength
    TUSB_DESC_CONFIGURATION,            // bDescriptorType
    CONFIG_TOTAL_LENGTH & 0xFF, CONFIG_TOTAL_LENGTH >> 8,
    1,                                  // bNumInterfaces
    1,                                  // bConfigurationValue
    0,                                  // iConfiguration
    0x80,                               // bmAttributes, bus powered
    TUSB_DESC_CONFIG_POWER_MA(200),     // bMaxPower

    // Interface, mass storage / SCSI transparent / bulk only
    9,                                  // bLength
    TUSB_DESC_INTERFACE,                // bDescriptorType
    0,                                  // bInterfaceNumber
    0,                                  // bAlternateSetting
    2,                                  // bNumEndpoints
    TUSB_CLASS_MSC,                     // bInterfaceClass
    0x06,                               // bInterfaceSubClass, SCSI transparent
    0x50,                               // bInterfaceProtocol, bulk only transport
    0,                                  // iInterface

    // Bulk OUT
    7,                                  // bLength
    TUSB_DESC_ENDPOINT,                 // bDescriptorType
    EP_MSC_OUT,                         // bEndpointAddress
    TUSB_XFER_BULK,                     // bmAttributes
    EP_BULK_PACKET_SIZE, 0x00,          // wMaxPacketSize
    0,                                  // bInterval

    // Bulk IN
    7,                                  // bLength
    TUSB_DESC_ENDPOINT,                 // bDescriptorType
    EP_MSC_IN,                          // bEndpointAddress
    TUSB_XFER_BULK,                     // bmAttributes
    EP_BULK_PACKET_SIZE, 0x00,          // wMaxPacketSize
    0                                   // bInterval
};

static const char* const sStringDescriptors[] =
{
    nullptr,        // 0, language id, handled separately
    "DSpico",       // 1, iManufacturer
    "microSD"       // 2, iProduct
};

//--------------------------------------------------------------------
// State
//--------------------------------------------------------------------

enum class CtrlStage : u8
{
    Idle,
    DataIn,     // sending the data stage to the host
    StatusIn,   // sending the zero length status packet
    StatusOut   // receiving the zero length status packet
};

enum class MscStage : u8
{
    WaitCbw,    // a command block is armed on the bulk OUT endpoint
    DataIn,     // sending data to the host
    DataOut,    // receiving data from the host
    SdRead,     // usbh_update() must read from the card
    SdWrite,    // usbh_update() must write to the card
    SendCsw     // sending the command status
};

struct TU_ATTR_PACKED msc_cbw_t
{
    u32 signature;
    u32 tag;
    u32 dataTransferLength;
    u8 flags;
    u8 lun;
    u8 cmdLength;
    u8 cmd[16];
};

struct TU_ATTR_PACKED msc_csw_t
{
    u32 signature;
    u32 tag;
    u32 dataResidue;
    u8 status;
};

#define MSC_CBW_SIGNATURE   0x43425355u
#define MSC_CSW_SIGNATURE   0x53425355u

#define MSC_CSW_STATUS_PASSED       0
#define MSC_CSW_STATUS_FAILED       1

#define SCSI_SENSE_NONE             0x00
#define SCSI_SENSE_NOT_READY        0x02
#define SCSI_SENSE_MEDIUM_ERROR     0x03
#define SCSI_SENSE_ILLEGAL_REQUEST  0x05
#define SCSI_SENSE_UNIT_ATTENTION   0x06

extern "C" volatile bool gUsbHostActive;
volatile bool gUsbHostActive;
static bool sConfigured;

static CtrlStage sCtrlStage;
static tusb_control_request_t sCtrlRequest;
static u8 sCtrlBuf[96] alignas(4);

// sMscStage and the transfer counters are written in the USB interrupt and in
// usbh_update() on the main loop, so they must not be cached in registers.
static volatile MscStage sMscStage;
static volatile bool sCswPending;
static msc_cbw_t sCbw alignas(4);
static msc_csw_t sCsw alignas(4);

static u8 sMscBuf[MSC_BUF_SECTORS * SD_SECTOR_SIZE] alignas(4);

static volatile u32 sLba;           // next card sector to transfer
static volatile u32 sBlocksLeft;    // sectors still to transfer for the current command
static volatile u32 sChunkBlocks;   // sectors in the transfer currently in flight
static volatile u32 sResidue;       // bytes the host asked for that will not be sent
static u32 sSectorCount;            // card size in sectors

static u8 sSenseKey;
static u8 sSenseAsc;
static u8 sSenseAscq;

//--------------------------------------------------------------------
// Helpers
//--------------------------------------------------------------------

static inline u32 readBe32(const u8* p)
{
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
}

static inline u32 readBe16(const u8* p)
{
    return ((u32)p[0] << 8) | p[1];
}

static inline void writeBe32(u8* p, u32 value)
{
    p[0] = value >> 24;
    p[1] = value >> 16;
    p[2] = value >> 8;
    p[3] = value;
}

static void setSense(u8 key, u8 asc, u8 ascq)
{
    sSenseKey = key;
    sSenseAsc = asc;
    sSenseAscq = ascq;
}

static void armCbw(void)
{
    sMscStage = MscStage::WaitCbw;
    dcd_edpt_xfer(0, EP_MSC_OUT, (u8*)&sCbw, sizeof(sCbw));
}

static void prepareCsw(u8 status, u32 residue)
{
    sCsw.signature = MSC_CSW_SIGNATURE;
    sCsw.tag = sCbw.tag;
    sCsw.dataResidue = residue;
    sCsw.status = status;
}

static void sendPreparedCsw(void)
{
    sCswPending = false;
    sMscStage = MscStage::SendCsw;
    dcd_edpt_xfer(0, EP_MSC_IN, (u8*)&sCsw, sizeof(sCsw));
}

static void sendCsw(u8 status, u32 residue)
{
    prepareCsw(status, residue);
    sendPreparedCsw();
}

/// Fails the current command. The host will ask why with REQUEST SENSE.
static void failCommand(u8 key, u8 asc, u8 ascq)
{
    setSense(key, asc, ascq);
    sBlocksLeft = 0;
    prepareCsw(MSC_CSW_STATUS_FAILED, sCbw.dataTransferLength);

    if (sCbw.dataTransferLength != 0)
    {
        // The host is expecting a data stage we are not going to provide. The bulk only
        // transport says to stall the data endpoint; the host then clears the stall and
        // reads the status. The status cannot be queued yet, because dcd_edpt_xfer
        // rewrites the endpoint's buffer control and would clear the stall bit.
        sCswPending = true;
        dcd_edpt_stall(0, (sCbw.flags & 0x80) != 0 ? EP_MSC_IN : EP_MSC_OUT);
    }
    else
    {
        sendPreparedCsw();
    }
}

/// Sends a short response that does not come from the card.
static void sendDataIn(u32 length)
{
    u32 wanted = sCbw.dataTransferLength;
    if (length > wanted)
    {
        length = wanted;
    }
    sBlocksLeft = 0;
    sChunkBlocks = 0;
    sResidue = wanted - length;
    sMscStage = MscStage::DataIn;
    dcd_edpt_xfer(0, EP_MSC_IN, sMscBuf, (u16)length);
}

//--------------------------------------------------------------------
// SCSI
//--------------------------------------------------------------------

static void scsiInquiry(void)
{
    memset(sMscBuf, 0, 36);
    sMscBuf[0] = 0x00;          // direct access block device
    sMscBuf[1] = 0x80;          // removable
    sMscBuf[2] = 0x02;          // SCSI-2
    sMscBuf[3] = 0x02;          // response data format
    sMscBuf[4] = 31;            // additional length
    memcpy(&sMscBuf[8], "DSpico  ", 8);
    memcpy(&sMscBuf[16], "microSD         ", 16);
    memcpy(&sMscBuf[32], "1.00", 4);
    sendDataIn(36);
}

static void scsiReadCapacity10(void)
{
    // The card was sized when it was initialized, so this needs no card access and
    // does not claim ownership.
    writeBe32(&sMscBuf[0], sSectorCount - 1);
    writeBe32(&sMscBuf[4], SD_SECTOR_SIZE);
    sendDataIn(8);
}

static void scsiRequestSense(void)
{
    memset(sMscBuf, 0, 18);
    sMscBuf[0] = 0x70;          // current error, fixed format
    sMscBuf[2] = sSenseKey;
    sMscBuf[7] = 10;            // additional sense length
    sMscBuf[12] = sSenseAsc;
    sMscBuf[13] = sSenseAscq;
    setSense(SCSI_SENSE_NONE, 0, 0);
    sendDataIn(18);
}

static void scsiModeSense6(void)
{
    memset(sMscBuf, 0, 4);
    sMscBuf[0] = 3;             // mode data length
    sMscBuf[1] = 0;             // medium type
    sMscBuf[2] = 0;             // not write protected
    sMscBuf[3] = 0;             // no block descriptors
    sendDataIn(4);
}

/// Sets up a multi sector read or write. The transfer itself happens in usbh_update().
static void scsiStartTransfer(bool write)
{
    u32 lba = readBe32(&sCbw.cmd[2]);
    u32 blocks = readBe16(&sCbw.cmd[7]);

    if (blocks == 0)
    {
        sendCsw(MSC_CSW_STATUS_PASSED, sCbw.dataTransferLength);
        return;
    }

    if (lba >= sSectorCount || blocks > sSectorCount - lba)
    {
        // Logical block address out of range.
        failCommand(SCSI_SENSE_ILLEGAL_REQUEST, 0x21, 0x00);
        return;
    }

    if (sCbw.dataTransferLength != blocks * SD_SECTOR_SIZE)
    {
        failCommand(SCSI_SENSE_ILLEGAL_REQUEST, 0x24, 0x00);
        return;
    }

    if (!card_tryClaim(CARD_OWNER_HOST))
    {
        // A DS got there first and is using the card. Refusing is the whole point:
        // serving the host as well would corrupt the filesystem. See cardOwner.h.
        failCommand(SCSI_SENSE_NOT_READY, 0x3A, 0x00);
        return;
    }

    sLba = lba;
    sBlocksLeft = blocks;
    sChunkBlocks = blocks < MSC_BUF_SECTORS ? blocks : MSC_BUF_SECTORS;
    sResidue = 0;

    if (write)
    {
        sMscStage = MscStage::DataOut;
        dcd_edpt_xfer(0, EP_MSC_OUT, sMscBuf, (u16)(sChunkBlocks * SD_SECTOR_SIZE));
    }
    else
    {
        sMscStage = MscStage::SdRead;
        __sev();
    }
}

static void scsiHandleCommand(void)
{
    switch (sCbw.cmd[0])
    {
        case 0x00:  // TEST UNIT READY
            if (card_isOwnedBy(CARD_OWNER_DS))
            {
                failCommand(SCSI_SENSE_NOT_READY, 0x3A, 0x00);
            }
            else
            {
                sendCsw(MSC_CSW_STATUS_PASSED, 0);
            }
            break;

        case 0x03:  // REQUEST SENSE
            scsiRequestSense();
            break;

        case 0x12:  // INQUIRY
            scsiInquiry();
            break;

        case 0x1A:  // MODE SENSE (6)
            scsiModeSense6();
            break;

        case 0x1B:  // START STOP UNIT
        case 0x1E:  // PREVENT ALLOW MEDIUM REMOVAL
            sendCsw(MSC_CSW_STATUS_PASSED, 0);
            break;

        case 0x25:  // READ CAPACITY (10)
            scsiReadCapacity10();
            break;

        case 0x28:  // READ (10)
            scsiStartTransfer(false);
            break;

        case 0x2A:  // WRITE (10)
            scsiStartTransfer(true);
            break;

        case 0x35:  // SYNCHRONIZE CACHE (10)
            // Writes are committed to the card before their status is reported, so
            // there is nothing buffered to flush.
            sendCsw(MSC_CSW_STATUS_PASSED, 0);
            break;

        default:
            // Invalid command operation code.
            failCommand(SCSI_SENSE_ILLEGAL_REQUEST, 0x20, 0x00);
            break;
    }
}

//--------------------------------------------------------------------
// Bulk only transport
//--------------------------------------------------------------------

static void mscOnCbwReceived(u32 length)
{
    if (length != sizeof(sCbw) || sCbw.signature != MSC_CBW_SIGNATURE)
    {
        // A malformed command block means the host and device are out of step. The
        // transport says to stall both endpoints until the host issues a reset.
        dcd_edpt_stall(0, EP_MSC_OUT);
        dcd_edpt_stall(0, EP_MSC_IN);
        return;
    }

    if (sCbw.lun != 0 || sCbw.cmdLength == 0 || sCbw.cmdLength > 16)
    {
        failCommand(SCSI_SENSE_ILLEGAL_REQUEST, 0x20, 0x00);
        return;
    }

    scsiHandleCommand();
}

static void mscOnBulkOutComplete(u32 length)
{
    switch (sMscStage)
    {
        case MscStage::WaitCbw:
            mscOnCbwReceived(length);
            break;

        case MscStage::DataOut:
            // Sector data has arrived. The card write is slow, so it happens in
            // usbh_update() rather than here in the interrupt.
            sMscStage = MscStage::SdWrite;
            __sev();
            break;

        default:
            break;
    }
}

static void mscOnBulkInComplete(void)
{
    switch (sMscStage)
    {
        case MscStage::DataIn:
            if (sBlocksLeft != 0)
            {
                sChunkBlocks = sBlocksLeft < MSC_BUF_SECTORS ? sBlocksLeft : MSC_BUF_SECTORS;
                sMscStage = MscStage::SdRead;
                __sev();
            }
            else
            {
                sendCsw(MSC_CSW_STATUS_PASSED, sResidue);
            }
            break;

        case MscStage::SendCsw:
            armCbw();
            break;

        default:
            break;
    }
}

//--------------------------------------------------------------------
// Control transfers
//--------------------------------------------------------------------

/// Builds a string descriptor in sCtrlBuf and returns its length.
static u32 buildStringDescriptor(u32 index)
{
    if (index == 0)
    {
        sCtrlBuf[0] = 4;
        sCtrlBuf[1] = TUSB_DESC_STRING;
        sCtrlBuf[2] = 0x09;     // English (United States)
        sCtrlBuf[3] = 0x04;
        return 4;
    }

    if (index >= TU_ARRAY_SIZE(sStringDescriptors) || sStringDescriptors[index] == nullptr)
    {
        return 0;
    }

    const char* str = sStringDescriptors[index];
    u32 chars = strlen(str);
    u32 maxChars = (sizeof(sCtrlBuf) - 2) / 2;
    if (chars > maxChars)
    {
        chars = maxChars;
    }

    sCtrlBuf[0] = (u8)(2 + chars * 2);
    sCtrlBuf[1] = TUSB_DESC_STRING;
    for (u32 i = 0; i < chars; i++)
    {
        sCtrlBuf[2 + i * 2] = (u8)str[i];
        sCtrlBuf[3 + i * 2] = 0;
    }
    return 2 + chars * 2;
}

static u32 buildDescriptor(u32 type, u32 index)
{
    switch (type)
    {
        case TUSB_DESC_DEVICE:
            memcpy(sCtrlBuf, sDeviceDescriptor, sizeof(sDeviceDescriptor));
            return sizeof(sDeviceDescriptor);

        case TUSB_DESC_CONFIGURATION:
            memcpy(sCtrlBuf, sConfigDescriptor, sizeof(sConfigDescriptor));
            return sizeof(sConfigDescriptor);

        case TUSB_DESC_STRING:
            return buildStringDescriptor(index);

        default:
            return 0;
    }
}

static void ctrlStall(void)
{
    dcd_edpt_stall(0, 0x80);
    dcd_edpt_stall(0, 0x00);
    sCtrlStage = CtrlStage::Idle;
}

static void ctrlSendData(u32 length)
{
    if (length > sCtrlRequest.wLength)
    {
        length = sCtrlRequest.wLength;
    }
    sCtrlStage = CtrlStage::DataIn;
    dcd_edpt_xfer(0, 0x80, sCtrlBuf, (u16)length);
}

static void ctrlSendStatus(void)
{
    sCtrlStage = CtrlStage::StatusIn;
    dcd_edpt_xfer(0, 0x80, nullptr, 0);
}

static void openMscEndpoints(void)
{
    tusb_desc_endpoint_t ep;
    memset(&ep, 0, sizeof(ep));
    ep.bLength = sizeof(tusb_desc_endpoint_t);
    ep.bDescriptorType = TUSB_DESC_ENDPOINT;
    ep.bmAttributes.xfer = TUSB_XFER_BULK;
    ep.wMaxPacketSize = EP_BULK_PACKET_SIZE;

    ep.bEndpointAddress = EP_MSC_OUT;
    dcd_edpt_open(0, &ep);

    ep.bEndpointAddress = EP_MSC_IN;
    dcd_edpt_open(0, &ep);
}

static void handleStandardRequest(void)
{
    switch (sCtrlRequest.bRequest)
    {
        case TUSB_REQ_GET_DESCRIPTOR:
        {
            u32 length = buildDescriptor(sCtrlRequest.wValue >> 8, sCtrlRequest.wValue & 0xFF);
            if (length == 0)
            {
                ctrlStall();
            }
            else
            {
                ctrlSendData(length);
            }
            break;
        }

        case TUSB_REQ_SET_ADDRESS:
            // The address is applied after the status stage completes, in
            // dcd_edpt0_status_complete().
            ctrlSendStatus();
            break;

        case TUSB_REQ_SET_CONFIGURATION:
            if (sCtrlRequest.wValue == 1)
            {
                openMscEndpoints();
                sConfigured = true;
                setSense(SCSI_SENSE_NONE, 0, 0);
                armCbw();
            }
            else
            {
                sConfigured = false;
                dcd_edpt_close_all(0);
            }
            ctrlSendStatus();
            break;

        case TUSB_REQ_GET_CONFIGURATION:
            sCtrlBuf[0] = sConfigured ? 1 : 0;
            ctrlSendData(1);
            break;

        case TUSB_REQ_GET_STATUS:
            sCtrlBuf[0] = 0;
            sCtrlBuf[1] = 0;
            ctrlSendData(2);
            break;

        case TUSB_REQ_GET_INTERFACE:
            sCtrlBuf[0] = 0;
            ctrlSendData(1);
            break;

        case TUSB_REQ_SET_INTERFACE:
            ctrlSendStatus();
            break;

        case TUSB_REQ_CLEAR_FEATURE:
            if (sCtrlRequest.bmRequestType_bit.recipient == TUSB_REQ_RCPT_ENDPOINT &&
                sCtrlRequest.wValue == TUSB_REQ_FEATURE_EDPT_HALT)
            {
                dcd_edpt_clear_stall(0, (u8)sCtrlRequest.wIndex);
                if (sCswPending)
                {
                    // The stall was the data stage of a failed command. Its status can
                    // go out now that the endpoint is running again.
                    sendPreparedCsw();
                }
            }
            ctrlSendStatus();
            break;

        case TUSB_REQ_SET_FEATURE:
            if (sCtrlRequest.bmRequestType_bit.recipient == TUSB_REQ_RCPT_ENDPOINT &&
                sCtrlRequest.wValue == TUSB_REQ_FEATURE_EDPT_HALT)
            {
                dcd_edpt_stall(0, (u8)sCtrlRequest.wIndex);
            }
            ctrlSendStatus();
            break;

        default:
            ctrlStall();
            break;
    }
}

static void handleClassRequest(void)
{
    switch (sCtrlRequest.bRequest)
    {
        case 0xFE:  // GET MAX LUN
            sCtrlBuf[0] = 0;
            ctrlSendData(1);
            break;

        case 0xFF:  // BULK ONLY MASS STORAGE RESET
            dcd_edpt_clear_stall(0, EP_MSC_OUT);
            dcd_edpt_clear_stall(0, EP_MSC_IN);
            sBlocksLeft = 0;
            sCswPending = false;
            armCbw();
            ctrlSendStatus();
            break;

        default:
            ctrlStall();
            break;
    }
}

//--------------------------------------------------------------------
// Interrupt entry points
//--------------------------------------------------------------------

extern "C" void usbh_onSetupReceived(const void* setupPacket)
{
    sCtrlRequest = *(const tusb_control_request_t*)setupPacket;
    sCtrlStage = CtrlStage::Idle;

    if (sCtrlRequest.bmRequestType_bit.type == TUSB_REQ_TYPE_STANDARD)
    {
        handleStandardRequest();
    }
    else if (sCtrlRequest.bmRequestType_bit.type == TUSB_REQ_TYPE_CLASS)
    {
        handleClassRequest();
    }
    else
    {
        ctrlStall();
    }
}

extern "C" void usbh_onXferComplete(u32 epAddr, u32 xferredLen)
{
    if (epAddr == 0x00 || epAddr == 0x80)
    {
        switch (sCtrlStage)
        {
            case CtrlStage::DataIn:
                // Data stage done, collect the status stage from the host.
                sCtrlStage = CtrlStage::StatusOut;
                dcd_edpt_xfer(0, 0x00, nullptr, 0);
                break;

            case CtrlStage::StatusIn:
            case CtrlStage::StatusOut:
                sCtrlStage = CtrlStage::Idle;
                dcd_edpt0_status_complete(0, &sCtrlRequest);
                break;

            default:
                break;
        }
        return;
    }

    if (epAddr == EP_MSC_OUT)
    {
        mscOnBulkOutComplete(xferredLen);
    }
    else if (epAddr == EP_MSC_IN)
    {
        mscOnBulkInComplete();
    }
}

extern "C" void usbh_onBusReset(void)
{
    sConfigured = false;
    sCtrlStage = CtrlStage::Idle;
    sMscStage = MscStage::WaitCbw;
    sBlocksLeft = 0;
    sCswPending = false;
    setSense(SCSI_SENSE_NONE, 0, 0);
}

extern "C" void usbh_onUnplugged(void)
{
    sConfigured = false;
    sCtrlStage = CtrlStage::Idle;
    sMscStage = MscStage::WaitCbw;
    sBlocksLeft = 0;
    sCswPending = false;
}

extern "C" void usbh_onSuspend(void)
{
}

extern "C" void usbh_onResume(void)
{
}

//--------------------------------------------------------------------
// Public interface
//--------------------------------------------------------------------

extern "C" void usbh_start(void)
{
    if (gUsbHostActive)
    {
        return;
    }

    sSectorCount = gSdCard.GetSectorCount();
    if (sSectorCount == 0)
    {
        return;
    }

    sConfigured = false;
    sCtrlStage = CtrlStage::Idle;
    sMscStage = MscStage::WaitCbw;
    sBlocksLeft = 0;
    sCswPending = false;
    setSense(SCSI_SENSE_NONE, 0, 0);

    // The flag must be set before dcd_init(), because dcd_init() connects the pull-up and
    // events can start arriving immediately. dcd_rp2040.c routes them here only while
    // this flag is set.
    gUsbHostActive = true;

    pwr_disableUsbPowerSaving();
    dcd_init(0, nullptr);
    dcd_int_enable(0);
}

extern "C" void usbh_stop(void)
{
    if (!gUsbHostActive)
    {
        return;
    }

    dcd_disconnect(0);
    dcd_int_disable(0);
    usb_hw->main_ctrl = USB_MAIN_CTRL_CONTROLLER_EN_RESET;
    usb_hw->sie_ctrl = 0;
    usb_hw->inte = 0;
    pwr_enableUsbPowerSaving();

    gUsbHostActive = false;
    sConfigured = false;
}

extern "C" void usbh_update(void)
{
    if (!gUsbHostActive)
    {
        return;
    }

    MscStage stage = sMscStage;
    if (stage != MscStage::SdRead && stage != MscStage::SdWrite)
    {
        return;
    }

    u32 bytes = sChunkBlocks * SD_SECTOR_SIZE;
    bool ok;
    if (stage == MscStage::SdRead)
    {
        ok = gSdCard.TryReadSectorsSync(sMscBuf, sLba, sChunkBlocks);
    }
    else
    {
        ok = gSdCard.TryWriteSectorsSync(sMscBuf, sLba, sChunkBlocks);
    }

    // A bus reset or a host reset can land while the card is busy, which abandons the
    // command. Do not queue a transfer for a command that no longer exists.
    u32 irqState = save_and_disable_interrupts();
    if (sMscStage != stage)
    {
        restore_interrupts(irqState);
        return;
    }

    if (!ok)
    {
        // Unrecovered read error, or write fault.
        failCommand(SCSI_SENSE_MEDIUM_ERROR, stage == MscStage::SdRead ? 0x11 : 0x03, 0x00);
        restore_interrupts(irqState);
        return;
    }

    sLba += sChunkBlocks;
    sBlocksLeft -= sChunkBlocks;

    if (stage == MscStage::SdRead)
    {
        sMscStage = MscStage::DataIn;
        dcd_edpt_xfer(0, EP_MSC_IN, sMscBuf, (u16)bytes);
    }
    else if (sBlocksLeft != 0)
    {
        sChunkBlocks = sBlocksLeft < MSC_BUF_SECTORS ? sBlocksLeft : MSC_BUF_SECTORS;
        sMscStage = MscStage::DataOut;
        dcd_edpt_xfer(0, EP_MSC_OUT, sMscBuf, (u16)(sChunkBlocks * SD_SECTOR_SIZE));
    }
    else
    {
        sendCsw(MSC_CSW_STATUS_PASSED, 0);
    }
    restore_interrupts(irqState);
}
