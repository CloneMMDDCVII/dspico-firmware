# DSpico: expose the microSD card to a host computer over USB
#
# STATUS: IMPLEMENTED on branch claude/project-thread-kme98u. Builds clean; NOT yet
# tested on hardware -- every scenario below is unverified until someone flashes it.
#
# Pierre's decisions: read-write, and fail safe on conflict ("even refuse to load for
# the DS, or stop working for computer"). The typical use is the cart plugged into a
# computer while not inside a DS.
#
# Scenarios tagged @question are still open decisions; the wording in them is my
# recommendation, not an agreed fact.
# Scenarios tagged @regression describe behaviour that exists today and must
# not change.
#
# "Host" means the computer the USB-C cable is plugged into.
# "Owner" means whichever side (host or DS) is allowed to touch the SD card.
# Sector means a 512-byte block; the firmware is 512-only (FF_MIN_SS = FF_MAX_SS).

Feature: microSD card reader over USB-C
  As someone with a DSpico plugged into a computer
  I want the cartridge to appear as a removable drive
  So that I can copy ROMs and saves on and off the card without a separate reader

  Background:
    Given a DSpico cartridge with RP2040 firmware built from this repository
    And the cartridge has a USB-C port whose data lines reach the host
    And exactly one side may own the SD card at any moment


  # ---------------------------------------------------------------------------
  # A. Deciding who owns the card
  # ---------------------------------------------------------------------------

  Scenario: A card is present and no DS is driving the cartridge bus
    Given a microSD card is inserted
    And the cartridge is powered from USB-C
    And no DS has asserted the cartridge reset line since power-on
    When the host enumerates the device
    Then the host sees one removable mass storage volume
    And the volume's contents are the contents of the microSD card

  @regression
  Scenario: No card is present
    Given no microSD card is inserted
    When the cartridge powers on
    Then the firmware reboots into the RP2040 bootrom
    And the host sees the RPI-RP2 drive for firmware updates
    # This is today's behaviour via reset_usb_boot(0, 0) at src/main.cpp:158.
    # It is the only way to flash the cart, so it must survive unchanged.

  Scenario: The cartridge is in a DS that is powered on
    Given a microSD card is inserted
    And a DS has asserted the cartridge reset line
    When the host is also connected over USB-C
    Then the DS owns the card
    And the host does not see a mass storage volume
    # The cart supports dual power, so cart-in-DS plus cable plugged in is a
    # real situation, not a corner case.

  Scenario: A DS wakes up while the host owns the card
    Given the host owns the card and has mounted the volume
    When a DS asserts the cartridge reset line and asks to read the card
    Then the host keeps the card
    And the DS is told the card is not ready, for as long as the host has it
    # Ownership is a latch, decided by whoever touches the card first and held
    # until the cartridge is power cycled. Handing over mid-session would mean the
    # other side still believes it owns filesystem state it no longer controls --
    # the host's cached FAT, or the firmware's mounted FATFS and open R4 file
    # handles -- and that corrupts the card. So the losing side is refused instead.
    # The DS still boots its ROM, because the ROM lives in the RP2040's flash and
    # not on the card; only SD-backed commands fail.

  Scenario: The host arrives while a DS is already using the card
    Given a DS has read or written the card
    When a computer is connected over USB-C
    Then the host is told the medium is not present
    And the DS keeps working normally

  @question @not-implemented
  Scenario: A card is inserted but has no filesystem the firmware can read
    Given a microSD card is inserted
    And the card is unformatted, or formatted as exFAT
    When the cartridge powers on with no DS attached
    Then the host sees one removable mass storage volume
    And the host can format the card over USB
    # NOT IMPLEMENTED. Today this reboots to BOOTSEL, because "card present" is
    # really "FatFs mounted" (src/main.cpp:124-159) and FF_FS_EXFAT is 0. A card
    # reader works on raw sectors and does not need FatFs at all, so we could do
    # better. I left the existing behaviour alone because changing it removes a
    # route to BOOTSEL that someone may be relying on deliberately, and that is a
    # behavioural decision rather than part of building the reader. Say the word
    # and it is a small follow-up.


  # ---------------------------------------------------------------------------
  # B. What the host sees
  # ---------------------------------------------------------------------------

  Scenario Outline: The reported capacity matches the card
    Given a <type> card of <size> is inserted
    When the host reads the volume's capacity
    Then the capacity reported is the card's full usable capacity

    Examples:
      | type  | size   |
      | SDSC  | 2 GB   |
      | SDHC  | 8 GB   |
      | SDHC  | 32 GB  |

  @question
  Scenario: The device identifies itself to the host
    Given the host enumerates the mass storage device
    Then the device reports a USB vendor and product ID that is not squatted on
    And the device reports a product string identifying it as a DSpico
    # STILL OPEN, and it blocks release rather than testing. The build uses the
    # pid.codes prototype IDs (0x1209/0x0001), which exist precisely for unreleased
    # work that needs to enumerate, and which must not ship. Before release the
    # project needs its own pid.codes allocation or a product ID reserved under the
    # Raspberry Pi vendor ID. See the TODO in src/usbHost.cpp.


  # ---------------------------------------------------------------------------
  # C. Reading
  # ---------------------------------------------------------------------------

  Scenario: The host reads a single sector
    Given the host owns the card
    When the host reads sector N
    Then the data returned is the data stored in sector N on the card

  Scenario: The host reads a long run of sectors
    Given the host owns the card
    When the host reads 64 consecutive sectors in one request
    Then all 64 sectors are returned in order
    And the firmware uses the card's sequential read path rather than 64 single reads
    # SdCard::TryBeginReadSectors already supports multi-sector and the state
    # machine already optimises sequential access. This scenario exists so we
    # actually use it instead of leaving throughput on the floor.

  Scenario: The host issues a request while the card is still busy
    Given the host owns the card
    And the card is in the middle of a read or write
    When the host issues another request
    Then the firmware does not drop or corrupt either request
    And the firmware does not busy-wait with the USB interrupt blocked
    # The existing FatFs glue does "while (!TryReadSectorsSync(...))"
    # (src/sd/fatfs/diskio.cpp). The MSC path must use the async API instead or
    # it will stall USB.


  # ---------------------------------------------------------------------------
  # D. Writing
  # ---------------------------------------------------------------------------

  Scenario: The host writes a sector
    Given the host owns the card
    When the host writes data to sector N
    Then the data is written to sector N on the card

  Scenario: The host flushes its cache
    Given the host owns the card
    And the host has written sectors that the firmware has not finished committing
    When the host issues a cache flush
    Then the firmware completes every pending write before reporting success
    And any open sequential write on the card is closed
    # As built, a write is committed to the card before its status is reported, so
    # there is never anything buffered for a flush to chase.

  Scenario: The host ejects the volume
    Given the host owns the card
    When the host ejects the volume
    Then every pending write is committed
    And the card is left in a consistent state


  # ---------------------------------------------------------------------------
  # E. Not breaking what already works
  # ---------------------------------------------------------------------------

  @regression
  Scenario: DS-side USB access still works
    Given the cartridge is in a DS
    And DS software drives USB over cartridge commands E8 to EB
    When that software initialises USB and opens endpoints
    Then it behaves exactly as it does today
    # dcd_rp2040.c currently routes every USB event into usbEventQueue for the DS
    # instead of to a local device stack. Giving the firmware its own stack means
    # touching that path, which is the main regression risk in this whole change.

  @regression
  Scenario: R4 emulation still works
    Given the cartridge is in a DS running R4 software
    When that software reads a ROM and writes a save
    Then it behaves exactly as it does today
    # The R4 path holds live FatFs state and open FIL handles
    # (src/ntrCardRomGameR4.cpp), including a pointer into sFatFs.win. This is
    # concrete evidence the two sides cannot share the card: host sector writes
    # would silently invalidate that state.

  @regression @needs-measurement
  Scenario: Idle power draw in a DS is unchanged
    Given the cartridge is in a DS with no USB cable attached
    When the firmware is idle
    Then power draw is no worse than the current firmware
    # The board is specified at roughly 57 mW idle, and pwr_initPowerSaving()
    # de-inits pll_usb and stops clk_usb to get there. Whatever we add must not
    # leave the USB block running when there is no host. I cannot verify this
    # without hardware.


  # ---------------------------------------------------------------------------
  # F. Things going wrong
  # ---------------------------------------------------------------------------

  Scenario: The card is removed while the host owns it
    Given the host owns the card
    When the card is physically removed
    Then the firmware reports the medium as absent rather than hanging
    And the host is not left waiting on a transfer that never completes

  Scenario: The card returns an error mid-transfer
    Given the host owns the card
    When an SD read or write fails
    Then the firmware reports a failure to the host
    And the firmware does not hit a breakpoint or spin forever
    # Several existing SD paths call __breakpoint() on failure
    # (src/ntrCardRomGameSd.cpp). That is fine for a debug build driven by a DS;
    # it is not acceptable on a path a host computer can trigger.


  # ---------------------------------------------------------------------------
  # Explicitly out of scope for this change
  # ---------------------------------------------------------------------------
  #
  # - Reading GPIO24 for VBUS, and dropping FORCE_VBUS_DETECT. We do not know
  #   whether that pin is wired on your USB-C board, and the design above does
  #   not need it. It stays a later power optimisation. As built, the USB block
  #   is powered up whenever a card mounts, which costs idle power in a DS; see
  #   the power scenario above, which needs measuring.
  # - Reporting a USB serial number. Deliberate; the reason is in src/usbHost.cpp.
  # - Any host-visible feature other than the card: no CDC serial, no HID.
  # - Presenting a synthetic or virtual filesystem. This exposes the card's real
  #   sectors, nothing else.
  # - Changing the SDIO layer or the cartridge bus emulation.
