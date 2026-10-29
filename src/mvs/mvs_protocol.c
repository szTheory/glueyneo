/* SPDX-License-Identifier: MIT */
/* Per-instance BIOS-to-cartridge protocol trace and attract/start verdict.
 *
 * Contract: docs/mvs-media.md "Attract/start predicate". Sources are the fetched
 * rows S1-S6 there (NeoGeo Development Wiki, community documentation) and S7
 * (pinned MAME, differential evidence); neither is hardware truth. The trace
 * records guest-performed writes to the three attract BIOS RAM variables,
 * the S29b BIOS P1 start indication, and documented USER/PLAYER_START entries, with the
 * region of the executing instruction. It reads no program bytes and keeps no
 * file-scope mutable state: every field lives in the caller's gn_mvs_protocol.
 */
#include "../sdk_private.h"

#include <string.h>

gn_mvs_pc_region gn_mvs_classify_pc(uint32_t pc) {
    pc &= UINT32_C(0x00ffffff);
    if (pc >= UINT32_C(0xc00000) && pc <= UINT32_C(0xcfffff)) return GN_MVS_PC_BIOS;
    if (pc <= UINT32_C(0x0fffff)) return GN_MVS_PC_CART_FIXED;
    if (pc >= UINT32_C(0x100000) && pc <= UINT32_C(0x10ffff)) return GN_MVS_PC_WORK_RAM;
    if (pc >= UINT32_C(0x200000) && pc <= UINT32_C(0x2fffff)) return GN_MVS_PC_CART_BANKED;
    return GN_MVS_PC_OTHER;
}

void gn_mvs_protocol_reset(gn_mvs_protocol *protocol) {
    if (protocol != NULL) memset(protocol, 0, sizeof(*protocol));
}

static int is_request_event(const gn_mvs_protocol_event *event) {
    return event->kind == GN_MVS_PROTOCOL_BIOS_VAR_WRITE &&
           event->address == GN_MVS_BIOS_USER_REQUEST;
}

static int is_cartridge_region(unsigned region) {
    return region == GN_MVS_PC_CART_FIXED || region == GN_MVS_PC_CART_BANKED;
}

static void append(gn_mvs_protocol *protocol, uint32_t address, unsigned kind,
                   uint8_t value, gn_mvs_pc_region region,
                   uint64_t input_sequence) {
    if (protocol->count > 0u) {
        const gn_mvs_protocol_event *last = &protocol->events[protocol->count - 1u];
        /* An identical consecutive event adds no information to an ordered
         * verdict, so it is coalesced instead of consuming a slot. */
        if (last->kind == kind && last->address == address &&
            last->value == value && last->writer_pc_region == region &&
            last->input_sequence == input_sequence) return;
    }
    if (protocol->count == GN_MVS_PROTOCOL_TRACE_CAPACITY) {
        if (protocol->dropped != UINT32_MAX) ++protocol->dropped;
        return;
    }
    gn_mvs_protocol_event *event = &protocol->events[protocol->count++];
    event->address = address;
    event->kind = (uint8_t)kind;
    event->value = value;
    event->writer_pc_region = (uint8_t)region;
    event->reserved = 0u;
    event->total_cycles = protocol->cycle_base;
    event->sequence = ++protocol->sequence;
    event->input_sequence = input_sequence;
}

void gn_mvs_protocol_note_write(gn_mvs_protocol *protocol, uint32_t address,
                                unsigned width_bytes, uint16_t value,
                                gn_mvs_pc_region writer_region) {
    if (protocol == NULL || protocol->guest_active == 0u) return;
    /* S29b: BIOS_START_FLAG identifies the player who pushed Start. Track
     * every overlapping write, including clears and cartridge writes, so a
     * stale or game-authored indication cannot qualify a later BIOS transfer.
     * A word at the even flag address supplies the high byte. */
    if (address == GN_MVS_BIOS_START_FLAG) {
        const uint8_t flag = width_bytes == 2u ? (uint8_t)(value >> 8) :
                                                 (uint8_t)value;
        protocol->bios_p1_start_input_sequence =
            writer_region == GN_MVS_PC_BIOS && (flag & 1u) != 0u &&
            protocol->start_input_sequence > protocol->coin_input_sequence &&
            protocol->coin_input_sequence > protocol->attract_input_sequence &&
            protocol->attract_start_reached != 0u ?
                protocol->start_input_sequence : 0u;
    }
    static const uint32_t variables[] = {
        GN_MVS_BIOS_SYSTEM_MODE, GN_MVS_BIOS_USER_REQUEST, GN_MVS_BIOS_USER_MODE};
    for (size_t index = 0u; index < sizeof(variables) / sizeof(variables[0]); ++index) {
        const uint32_t variable = variables[index];
        uint8_t byte;
        if (variable == address) {
            byte = width_bytes == 2u ? (uint8_t)(value >> 8) : (uint8_t)value;
        } else if (width_bytes == 2u && variable == address + 1u) {
            byte = (uint8_t)value;
        } else {
            continue;
        }
        if (protocol->decided != 0u) {
            /* After the decision only the optional corroboration is tracked,
             * so later BIOS or game traffic cannot overflow the ring. */
            if (variable == GN_MVS_BIOS_USER_MODE &&
                byte == GN_MVS_USER_MODE_TITLE_DEMO &&
                is_cartridge_region(writer_region)) {
                protocol->corroborated = 1u;
            }
            continue;
        }
        append(protocol, variable, GN_MVS_PROTOCOL_BIOS_VAR_WRITE, byte,
               writer_region, 0u);
    }
}

void gn_mvs_protocol_note_user_entry(gn_mvs_protocol *protocol) {
    /* Called by gn_run_mvs between instructions, never from a host test hook,
     * so it does not depend on guest_active (which gates bus-callback writes). */
    if (protocol == NULL || protocol->decided != 0u) return;
    append(protocol, GN_MVS_USER_ENTRY, GN_MVS_PROTOCOL_USER_ENTRY_FETCH, 0u,
           gn_mvs_classify_pc(GN_MVS_USER_ENTRY), 0u);
    const gn_mvs_attract_verdict verdict = gn_mvs_protocol_verdict(protocol);
    if (verdict.accepted != 0u) {
        protocol->decided = 1u;
        protocol->attract_start_reached = 1u;
        protocol->user_request = verdict.user_request;
        protocol->attract_input_sequence = protocol->input_sequence;
    }
}

void gn_mvs_protocol_note_input_change(gn_mvs_protocol *protocol,
                                       uint32_t previous_mask,
                                       uint32_t next_mask) {
    if (protocol == NULL || previous_mask == next_mask) return;
    if (protocol->input_sequence != UINT64_MAX) ++protocol->input_sequence;
    if ((previous_mask & GN_MVS_INPUT_COIN1) == 0u &&
        (next_mask & GN_MVS_INPUT_COIN1) != 0u) {
        protocol->coin_input_sequence = protocol->input_sequence;
    }
    if ((previous_mask & GN_MVS_INPUT_P1_START) == 0u &&
        (next_mask & GN_MVS_INPUT_P1_START) != 0u) {
        protocol->start_input_sequence = protocol->input_sequence;
    }
}

void gn_mvs_protocol_note_player_start(gn_mvs_protocol *protocol) {
    if (protocol == NULL) return;
    protocol->player_start_entered = 1u;
    protocol->player_start_input_sequence = protocol->input_sequence;
    if (protocol->attract_start_reached != 0u &&
        protocol->coin_input_sequence > protocol->attract_input_sequence &&
        protocol->start_input_sequence > protocol->coin_input_sequence &&
        protocol->bios_p1_start_input_sequence == protocol->start_input_sequence &&
        protocol->player_start_input_sequence >= protocol->start_input_sequence) {
        protocol->player_start_with_p1_indication = 1u;
    }
    /* The attract verdict is already final at this point. Preserve its trace
     * overflow result if the bounded event ring is full; the public progress
     * fields above still record the later guest transfer. */
    if (protocol->count < GN_MVS_PROTOCOL_TRACE_CAPACITY) {
        append(protocol, GN_MVS_PLAYER_START_ENTRY,
               GN_MVS_PROTOCOL_PLAYER_START_FETCH, 0u,
               gn_mvs_classify_pc(GN_MVS_PLAYER_START_ENTRY),
               protocol->player_start_input_sequence);
    }
}

gn_mvs_attract_verdict gn_mvs_protocol_verdict(const gn_mvs_protocol *protocol) {
    gn_mvs_attract_verdict verdict;
    memset(&verdict, 0, sizeof(verdict));
    if (protocol == NULL) {
        verdict.rejection = GN_MVS_ATTRACT_NO_REQUEST;
        return verdict;
    }
    if (protocol->dropped > 0u) {
        verdict.rejection = GN_MVS_ATTRACT_TRACE_OVERFLOW;
        return verdict;
    }
    const gn_mvs_protocol_event *latest_request = NULL;
    const gn_mvs_protocol_event *last_entry = NULL;
    const gn_mvs_protocol_event *request_before_last_entry = NULL;
    int any_request = 0;
    for (uint32_t index = 0u; index < protocol->count; ++index) {
        const gn_mvs_protocol_event *event = &protocol->events[index];
        if (is_request_event(event)) {
            latest_request = event;
            any_request = 1;
            continue;
        }
        if (event->kind != GN_MVS_PROTOCOL_USER_ENTRY_FETCH) continue;
        last_entry = event;
        request_before_last_entry = latest_request;
        if (latest_request != NULL &&
            latest_request->writer_pc_region == GN_MVS_PC_BIOS &&
            (latest_request->value == GN_MVS_REQUEST_DEMO ||
             latest_request->value == GN_MVS_REQUEST_TITLE)) {
            verdict.accepted = 1u;
            verdict.rejection = GN_MVS_ATTRACT_NONE;
            verdict.user_request = latest_request->value;
            verdict.user_mode_corroborated = protocol->corroborated;
            verdict.request_sequence = latest_request->sequence;
            verdict.entry_sequence = event->sequence;
            verdict.entry_total_cycles = event->total_cycles;
            return verdict;
        }
    }
    if (!any_request) {
        verdict.rejection = GN_MVS_ATTRACT_NO_REQUEST;
        return verdict;
    }
    /* Not accepted. With an entry already seen, explain that entry; with none
     * yet, the verdict is pending unless the newest request is already wrong. */
    const gn_mvs_protocol_event *subject =
        last_entry != NULL ? request_before_last_entry : latest_request;
    if (subject == NULL) {
        verdict.rejection = GN_MVS_ATTRACT_WRONG_ORDER;
    } else if (subject->writer_pc_region != GN_MVS_PC_BIOS) {
        verdict.rejection = GN_MVS_ATTRACT_WRONG_SOURCE;
    } else if (subject->value != GN_MVS_REQUEST_DEMO &&
               subject->value != GN_MVS_REQUEST_TITLE) {
        verdict.rejection = GN_MVS_ATTRACT_WRONG_VALUE;
    }
    return verdict;
}

const char *gn_private_mvs_attract_rejection_name(unsigned rejection) {
    switch (rejection) {
    case GN_MVS_ATTRACT_NONE: return "NONE";
    case GN_MVS_ATTRACT_NO_REQUEST: return "NO_REQUEST";
    case GN_MVS_ATTRACT_WRONG_VALUE: return "WRONG_VALUE";
    case GN_MVS_ATTRACT_WRONG_SOURCE: return "WRONG_SOURCE";
    case GN_MVS_ATTRACT_WRONG_ORDER: return "WRONG_ORDER";
    case GN_MVS_ATTRACT_TRACE_OVERFLOW: return "TRACE_OVERFLOW";
    default: return "UNKNOWN";
    }
}

/* Stall counters. They only count what guest instructions did; a counter that
 * would wrap saturates instead. docs/mvs-media.md "Stall diagnosis". */
static void add_saturating(uint64_t *counter, uint64_t amount) {
    *counter = amount > UINT64_MAX - *counter ? UINT64_MAX : *counter + amount;
}

static int in_public_register_window(uint32_t address) {
    return (address >= UINT32_C(0x300000) && address <= UINT32_C(0x3fffff)) ||
           (address >= UINT32_C(0x2fffe0) && address <= UINT32_C(0x2fffff));
}

void gn_mvs_protocol_note_read(gn_mvs_protocol *protocol, uint32_t address) {
    if (protocol == NULL || protocol->guest_active == 0u) return;
    address &= UINT32_C(0x00ffffff);
    if (address >= UINT32_C(0x000080) && address <= UINT32_C(0x0fffff)) {
        add_saturating(&protocol->low_program_window_reads, 1u);
        return;
    }
    if (!in_public_register_window(address)) return;
    for (uint32_t index = 0u; index < protocol->polled_count; ++index) {
        if (protocol->polled[index].address == address) {
            add_saturating(&protocol->polled[index].reads, 1u);
            return;
        }
    }
    if (protocol->polled_count == GN_MVS_POLLED_TABLE_CAPACITY) {
        add_saturating(&protocol->polled_untracked_reads, 1u);
        return;
    }
    protocol->polled[protocol->polled_count].address = address;
    protocol->polled[protocol->polled_count].reads = 1u;
    ++protocol->polled_count;
}

void gn_mvs_protocol_note_read_fault(gn_mvs_protocol *protocol) {
    if (protocol == NULL || protocol->guest_active == 0u) return;
    add_saturating(&protocol->unmapped_read_count, 1u);
}

void gn_mvs_protocol_note_irq_ack(gn_mvs_protocol *protocol) {
    if (protocol == NULL || protocol->guest_active == 0u) return;
    add_saturating(&protocol->irq_ack_writes, 1u);
}

void gn_mvs_protocol_note_step(gn_mvs_protocol *protocol, unsigned sr_mask,
                               gn_mvs_pc_region pc_region,
                               uint64_t instructions, int interrupt_taken) {
    if (protocol == NULL) return;
    add_saturating(&protocol->sr_mask_histogram[sr_mask % GN_MVS_SR_MASK_BUCKETS],
                   instructions);
    if ((unsigned)pc_region < GN_MVS_PC_REGION_BUCKETS)
        add_saturating(&protocol->pc_region_histogram[pc_region], instructions);
    if (interrupt_taken != 0) add_saturating(&protocol->interrupts_taken, 1u);
}

void gn_mvs_protocol_diagnose(const gn_mvs_protocol *protocol,
                              gn_mvs_stall_diagnosis *out) {
    if (out == NULL) return;
    memset(out, 0, sizeof(*out));
    if (protocol == NULL) return;
    out->interrupts_taken = protocol->interrupts_taken;
    out->irq_ack_writes = protocol->irq_ack_writes;
    memcpy(out->sr_mask_histogram, protocol->sr_mask_histogram,
           sizeof(out->sr_mask_histogram));
    memcpy(out->pc_region_histogram, protocol->pc_region_histogram,
           sizeof(out->pc_region_histogram));
    out->low_program_window_reads = protocol->low_program_window_reads;
    out->unmapped_read_count = protocol->unmapped_read_count;
    out->polled_untracked_reads = protocol->polled_untracked_reads;
    out->attract_rejection = gn_mvs_protocol_verdict(protocol).rejection;
    /* Top rows by read count, ties by ascending address; selection from the
     * fixed table keeps the report at most 8 rows. */
    uint8_t taken[GN_MVS_POLLED_TABLE_CAPACITY] = {0};
    for (uint32_t row = 0u; row < GN_MVS_POLLED_REPORT_ROWS; ++row) {
        int best = -1;
        for (uint32_t index = 0u; index < protocol->polled_count; ++index) {
            if (taken[index] != 0u) continue;
            if (best < 0 || protocol->polled[index].reads > protocol->polled[best].reads ||
                (protocol->polled[index].reads == protocol->polled[best].reads &&
                 protocol->polled[index].address < protocol->polled[best].address))
                best = (int)index;
        }
        if (best < 0) break;
        taken[best] = 1u;
        out->polled[row] = protocol->polled[best];
        ++out->polled_count;
    }
}
