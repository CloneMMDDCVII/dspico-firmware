#pragma once
#include "common.h"

/// Exposes the SD card to a USB host as a mass storage device.
///
/// This is separate from the USB support in ntrCardRomGameUsb.cpp. There, the RP2040 is
/// only a USB device controller and the DS drives it over the cartridge bus, so the DS
/// owns the descriptors, the control transfers and the class logic. Here the firmware
/// drives USB itself. Only one of the two can be active at a time, because there is a
/// single USB device controller; usbh_isActive() says which.

#ifdef __cplusplus
extern "C" {
#endif

/// Set by usbh_start() and cleared by usbh_stop(). Exposed so that usbh_isActive() can
/// inline: it is tested in the USB interrupt on the DS side path too, and that handler is
/// deliberately kept out of flash (see __tusb_irq_path_func), so a call into flash there
/// would cost the DS exactly the latency that annotation exists to avoid.
extern volatile bool gUsbHostActive;

/// @brief Brings the mass storage device up. The card must already be initialized.
///        If no host is attached nothing enumerates and this costs only the USB clocks.
void usbh_start(void);

/// @brief Tears the mass storage device down and returns the USB block to its
///        powered-down state.
void usbh_stop(void);

/// @brief Moves pending SD data for the host. Must be pumped from the main loop;
///        SD transfers are far too slow to run in the USB interrupt.
void usbh_update(void);

//--------------------------------------------------------------------
// Called from the USB interrupt by dcd_rp2040.c when the firmware owns USB.
//--------------------------------------------------------------------

/// @brief Handles a bus reset from the host.
void usbh_onBusReset(void);

/// @brief Handles an 8 byte USB SETUP packet.
/// @param setupPacket The setup packet, as a \c tusb_control_request_t.
void usbh_onSetupReceived(const void* setupPacket);

/// @brief Handles completion of an endpoint transfer.
/// @param epAddr The endpoint address.
/// @param xferredLen The number of bytes transferred.
void usbh_onXferComplete(u32 epAddr, u32 xferredLen);

/// @brief Handles the host disconnecting.
void usbh_onUnplugged(void);

/// @brief Handles the bus being suspended.
void usbh_onSuspend(void);

/// @brief Handles the bus resuming.
void usbh_onResume(void);

#ifdef __cplusplus
}
#endif

/// @brief Returns whether the firmware is driving USB itself as a mass storage device.
/// @return \c true when the firmware owns the USB device controller, or \c false when
///         it is available to DS software.
static inline bool usbh_isActive(void)
{
    return gUsbHostActive;
}
