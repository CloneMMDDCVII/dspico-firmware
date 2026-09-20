# Scope for per-folder cover art, and for marking the system folders as system folders.
#
# Two things were confirmed by reading the launcher source on develop at dc64a34, and both
# change what this work is worth doing:
#
#   1. icon.bmp and cover.bmp are shown in DIFFERENT PLACES, so they are not alternatives.
#      In the banner-list and the two icon-grid layouts, icon.bmp is the small picture in
#      the browser on the bottom screen, and cover.bmp is the large preview of whatever is
#      selected, drawn on the TOP screen (RomBrowserTopScreenView.cpp uploads it to
#      GFX_BG_SUB + 0x4000). Only in the CoverFlow layout does cover.bmp become the bottom
#      screen carousel itself, via the 3D texture path in CoverView.cpp.
#
#      So in whichever layout Pierre ends up using, every folder he lands on will have
#      artwork on both screens, and neither file makes the other redundant.
#
#   2. The usable width of a cover is 106 pixels, not 128. docs/Customization.md says the
#      top-left 106x96 is used and the rest is right-hand padding. Note for anyone reading
#      the source later: FileCoverBitmapToTiledCopy.s actually copies 14 tiles across, so
#      112 columns reach VRAM. The extra 6 are not displayed. 106 is the number to design
#      to; 128x96 is still the number the file must declare, or BmpHeader::Validate rejects
#      it outright.
#
# The open design question is deliberately left as a Scenario below rather than settled
# here, because the two readings of Pierre's request lead to visibly different sets.

Feature: Folder artwork that tells the user which folders are theirs
  As someone handing this cart to other people, including children
  I want the folders that are mine to look inviting and the folders that are plumbing to
    look like plumbing
  So that nobody has to be told twice which ones to leave alone

  Background:
    Given the eight folders in scope are EZ5Shell, Games, Games/Enfance, _gba, _nds,
      _pico, ROMDAT and SAVE
    And Games and Games/Enfance are the only two the user is meant to browse
    And the other six are system folders
    And each of the eight already has a 32x32 4bpp icon.bmp delivered on 20 Sep 2026

  Scenario: Every folder in scope gains a cover
    Given a cover is a .bmp of 128x96 pixels at 8bpp
    When a cover is generated for a folder
    Then its DIB header must be 40 bytes, uncompressed, with a 256-entry palette
    And biClrUsed must be 0 or 256, because BmpHeader::Validate rejects anything else
    And all meaningful content must fall inside the top-left 106x96
    And the remaining 22 columns must be padding that no one will see
    And the cover must read as the same thing as that folder's icon, not as unrelated art

  Scenario: The system folders are marked as system folders
    Given six of the eight folders are plumbing
    When their artwork is generated
    Then each must carry a gear, consistently placed and consistently coloured across all
      six, so the marking is recognisable as a marking rather than as decoration
    And Games and Games/Enfance must carry no gear at all
    And the distinction must survive at 32x32, which is the size that actually has to do
      the work

  Scenario: The gear does not eat the thing it is marking
    Given a 32x32 icon at 4bpp is roughly a thousand pixels and sixteen colours
    When a gear is combined with a folder's existing symbol at that size
    Then the result must still be distinguishable from the other five gear-marked folders
      at a glance
    And a treatment that makes all six read as "a gear" first must be rejected, because
      the stated goal is that every folder guides the user
    And both candidate treatments must be rendered and compared before either is delivered

  Scenario: The 106x96 cover is allowed to be less cramped than the icon
    Given a cover has about ten times the area of an icon and sixteen times the colours
    When the same subject is drawn at cover size
    Then it may use the fuller composition that does not fit at 32x32
    And it must still be recognisably the same symbol as the icon, so the two screens agree

  Scenario: Real logos are used only where they survive the format
    Given Pierre suggested downloading brand or project icons from their sources
    When a folder corresponds to an actual project or product
    Then a real logo may be used at cover size where 106x96 and 256 colours can carry it
    And a drawn glyph must be preferred at icon size, where a downscaled logo to 32x32 at
      16 colours reliably turns to mush
    And folders that correspond to no project at all must be drawn, not sourced
    And the artwork is for Pierre's own card and is not redistributed

  Scenario: Nothing is delivered that the launcher will silently ignore
    Given a malformed BMP is rejected by the launcher without any error shown to the user
    When the set is complete
    Then every file must be parsed back with the launcher's own validation rules applied
    And the palette, dimensions, bit depth, compression and data offset must all be
      checked, not assumed
    And a preview of the whole set as the DS will render it must be produced for approval

  Scenario: The set reaches Pierre in a form he can install
    Given attachment cards do not reach him and this session cannot upload files
    When the set is finished
    Then it must be delivered the same way as the icons, as a download from his own repo
      with a checksum to verify
    And it must unzip straight onto the card root with each file already in its folder

  # Explicitly out of scope
  #
  #   - banner.bnr. It overrides the folder's displayed name as well as its icon, which is
  #     a bigger change than asked for.
  #   - Per-game covers under /_pico/covers/. This is about folders.
  #   - Anything that requires a launcher newer than develop at dc64a34.
  #
  # Standing caveat, unchanged: none of the per-folder art works on Pierre's installed
  # launcher. It all needs the develop build.
