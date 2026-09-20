# Scope for putting a custom image on the Pico Launcher boot splash.
#
# Context that shapes this. The splash is compiled in, not read from the SD card:
# arm9/gfx/splashTop.png is converted by grit into tiles, a tilemap and a palette, and
# App::DisplaySplashScreen DMAs them into sub BG VRAM. The grit options (-gt -gB8 -mRtpf
# -mp0 -p -mLs) mean 8bpp tiles with the tilemap deduplicating identical tiles, including
# flipped ones.
#
# The binding constraint is VRAM layout, not image quality. REG_BG1CNT_SUB = 0x0680 puts
# the character base at 0 and the screen base at block 6, so the tilemap starts 0x3000
# bytes into the same region the tiles occupy. At 64 bytes per 8bpp tile that leaves room
# for 192 unique tiles. The stock splash uses 149. Pierre's image reduces to 562, and
# reducing its colour depth does not help: it is still 404 tiles at 8 colours and only
# fits at 4 colours, which destroys the picture.
#
# So the image is not the problem to solve. The tile budget is.

Feature: A custom boot splash on the Pico Launcher
  As someone who has built their own DSpico cart
  I want my own artwork on the screen that shows before the launcher loads
  So that the cart feels like mine from the moment it boots

  Background:
    Given the launcher draws its boot splash from compiled-in tile, map and palette data
    And sub BG VRAM is VRAM C, 128KB mapped at 0x06200000
    And only the splash background is on screen at that moment

  Scenario: The tilemap stops colliding with the tile data
    Given the tilemap currently sits at offset 0x3000, capping the splash at 192 tiles
    When the screen base is moved above the largest possible tile set
    Then a full screen of 768 unique tiles must fit without overwriting the map
    And the change must be confined to the screen base in REG_BG1CNT_SUB and the matching
      destination offset in the tilemap DMA
    And the total VRAM used must stay within the 128KB of VRAM C

  Scenario: An arbitrary image becomes a usable splash asset
    Given a source image supplied as any common format
    When it is prepared for the launcher build
    Then it must be 256x192, the size of one DS screen
    And it must be 8-bit indexed with no more than 256 colours, which is what grit expects
    And it must carry no alpha channel, because the splash is opaque
    And it must be written to arm9/gfx/splashTop.png so the existing .grit file applies
      unchanged

  Scenario: The result is checked before it reaches hardware
    Given a prepared splashTop.png
    When its tile reduction is measured the way grit would perform it
    Then the unique tile count must be reported against the budget
    And a count that exceeds the budget must fail loudly rather than produce a build that
      corrupts the screen at runtime

  Scenario: Colour fidelity is reported honestly
    Given quantising to 256 colours changes how the image looks
    When the asset is prepared
    Then a preview of the quantised result must be produced for approval
    And the preview must be reviewed before anything is built

  Scenario: The work is delivered in a form Pierre can build
    Given the DS toolchain is not reachable from Claude's environment
    When the change is finished
    Then it must be delivered as a patch against pico-launcher plus the prepared PNG
    And the build steps must be stated for a machine that has BlocksDS installed
    And nothing may be pushed to the upstream pico-launcher repository

  Scenario: The original remains recoverable
    Given the stock splash is part of the upstream repository
    When the custom splash replaces it
    Then reverting must be a matter of discarding the patch and restoring the original PNG

  # Explicitly out of scope
  #
  #   - The in-launcher theme graphics (topbg.bin and friends). Those are read from the SD
  #     card at runtime and are a separate job.
  #   - Building pico-launcher inside Claude's environment. BlocksDS is unreachable here.
  #   - Any change to the DSpico firmware, which is a different repository.
  #   - The bottom-screen splash, unless asked for separately.
