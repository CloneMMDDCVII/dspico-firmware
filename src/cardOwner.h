#pragma once
#include "common.h"
#include "hardware/sync.h"

/// @brief The sides that can own the SD card.
typedef enum
{
    CARD_OWNER_NONE = 0,
    CARD_OWNER_DS,
    CARD_OWNER_HOST
} card_owner_t;

#ifdef __cplusplus
extern "C" {
#endif

extern volatile card_owner_t gCardOwner;

#ifdef __cplusplus
}
#endif

/// @brief Claims the card for one side. The first side to claim keeps the card until
///        the cartridge is power cycled.
///
/// The card cannot be handed over mid-session. Both sides keep state that the other
/// would invalidate: the host caches filesystem structures it expects to still own,
/// and the firmware keeps a mounted FATFS plus open FIL handles for R4 emulation
/// (see ntrCardRomGameR4.cpp). Swapping owners would corrupt the card, so a losing
/// side is refused instead.
///
/// @param owner The side asking for the card.
/// @return \c true if \p owner may use the card, or \c false if the other side has it.
static inline bool card_tryClaim(card_owner_t owner)
{
    // Claims come from both the PIO0 and USB interrupts, which preempt each other,
    // so the test and set have to be atomic. Both run on core0; core1 only generates
    // scrambler values and never touches the card.
    u32 irqState = save_and_disable_interrupts();
    if (gCardOwner == CARD_OWNER_NONE)
    {
        gCardOwner = owner;
    }
    bool ours = gCardOwner == owner;
    restore_interrupts(irqState);
    return ours;
}

/// @brief Returns whether the given side currently owns the card.
/// @param owner The side to check.
/// @return \c true if \p owner owns the card, or \c false otherwise.
static inline bool card_isOwnedBy(card_owner_t owner)
{
    return gCardOwner == owner;
}
