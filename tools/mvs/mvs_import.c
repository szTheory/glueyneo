/* SPDX-License-Identifier: MIT */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <zlib.h>

#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <sys/stat.h>
#include <windows.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

enum { IMPORT_OK, IMPORT_MALFORMED, IMPORT_UNSUPPORTED, IMPORT_LIMIT,
       IMPORT_PROFILE, IMPORT_DECOMPRESS, IMPORT_MEMORY, IMPORT_AMBIGUOUS };

#define ZIP_ENTRIES_MAX 6u
#define SOURCE_ENTRIES_MAX 64u
#define SOURCE_ZIP_MAX (96u * 1024u * 1024u)
#define ZIP_INPUT_MAX (64u * 1024u * 1024u)
#define REGION_MAX (48u * 1024u * 1024u)
#define OUTPUT_MAX (64u * 1024u * 1024u)
#define BUNDLE_HEADER 16u
#define BUNDLE_ENTRY_HEADER 12u

typedef struct {
    uint32_t role;
    uint32_t crc;
    uint32_t compressed;
    uint32_t expanded;
    uint32_t method;
    uint32_t data_offset;
    uint32_t extent_start;
    uint32_t extent_end;
    char name[64];
} zip_entry;

typedef struct {
    const char *name;
    uint32_t size;
    uint32_t role;
    uint32_t destination;
    uint32_t transform;
    uint32_t crc;
    const char *sha1;
} source_member;

enum { TRANSFORM_COPY, TRANSFORM_WORD_SWAP, TRANSFORM_EVEN, TRANSFORM_ODD };

static const source_member selected_sources[] = {
    {"250-p1.p1", 0x100000u, 2u, 0x000000u, TRANSFORM_WORD_SWAP, 0x81f1f60bu, "4c19f2e9824e606178ac1c9d4b0516fbaa625035"},
    {"250-p2.ep1", 0x400000u, 2u, 0x100000u, TRANSFORM_WORD_SWAP, 0x1fda2e12u, "18aaa7a3ba8da99f78c430e9be69ccde04bc04d9"},
    {"250-s1.s1", 0x020000u, 3u, 0u, TRANSFORM_COPY, 0xfb6f441du, "2cc392ecde5d5afb28ddbaa1030552b48571dcfb"},
    {"250-m1.m1", 0x020000u, 4u, 0u, TRANSFORM_COPY, 0xfd42a842u, "55769bad4860f64ef53a333e0da9e073db483d6a"},
    {"250-v1.v1", 0x400000u, 5u, 0x000000u, TRANSFORM_COPY, 0xc79ede73u, "ebfcc67204ff9677cf7972fd5b6b7faabf07280c"},
    {"250-v2.v2", 0x400000u, 5u, 0x400000u, TRANSFORM_COPY, 0xea9aabe1u, "526c42ca9a388f7435569400e2f132e2724c71ff"},
    {"250-v3.v3", 0x200000u, 5u, 0x800000u, TRANSFORM_COPY, 0x2ca65102u, "45979d1edb1fc774a415d9386f98d7cb252a2043"},
    {"250-c1.c1", 0x800000u, 6u, 0x0000000u, TRANSFORM_EVEN, 0x09a52c6fu, "c3e8a8ccdac0f8bddc4c3413277626532405fae2"},
    {"250-c2.c2", 0x800000u, 6u, 0x0000000u, TRANSFORM_ODD, 0x31679821u, "554f600a3aa09c16c13c625299b087a79d0d15c5"},
    {"250-c3.c3", 0x800000u, 6u, 0x1000000u, TRANSFORM_EVEN, 0xfd602019u, "c56646c62387bc1439d46610258c755beb8d7dd8"},
    {"250-c4.c4", 0x800000u, 6u, 0x1000000u, TRANSFORM_ODD, 0x31354513u, "31be8ea2498001f68ce4b06b8b90acbf2dcab6af"},
    {"250-c5.c5", 0x800000u, 6u, 0x2000000u, TRANSFORM_EVEN, 0xa4b56124u, "d41069856df990a1a99d39fb263c8303389d5475"},
    {"250-c6.c6", 0x800000u, 6u, 0x2000000u, TRANSFORM_ODD, 0x83e3e69du, "39be66287696829d243fb71b3fb8b7dc2bc3298f"},
};

static const source_member selected_bios = {
    "sp-s2.sp1", 0x20000u, 1u, 0u, TRANSFORM_WORD_SWAP,
    0x9036d879u, "4f5ed7105b7128794654ce82b51723e16e389543"
};

typedef struct {
    uint32_t state[5];
    uint64_t bytes;
    uint8_t block[64];
    size_t used;
} sha1_context;

static uint32_t rol32(uint32_t value, unsigned count) {
    return (value << count) | (value >> (32u - count));
}
static void sha1_transform(sha1_context *context, const uint8_t block[64]) {
    uint32_t w[80];
    for (size_t i = 0u; i < 16u; ++i)
        w[i] = ((uint32_t)block[i * 4u] << 24) | ((uint32_t)block[i * 4u + 1u] << 16) |
               ((uint32_t)block[i * 4u + 2u] << 8) | block[i * 4u + 3u];
    for (size_t i = 16u; i < 80u; ++i) w[i] = rol32(w[i - 3u] ^ w[i - 8u] ^ w[i - 14u] ^ w[i - 16u], 1u);
    uint32_t a = context->state[0], b = context->state[1], c = context->state[2], d = context->state[3], e = context->state[4];
    for (size_t i = 0u; i < 80u; ++i) {
        uint32_t f, k;
        if (i < 20u) { f = (b & c) | (~b & d); k = 0x5a827999u; }
        else if (i < 40u) { f = b ^ c ^ d; k = 0x6ed9eba1u; }
        else if (i < 60u) { f = (b & c) | (b & d) | (c & d); k = 0x8f1bbcdcu; }
        else { f = b ^ c ^ d; k = 0xca62c1d6u; }
        const uint32_t temp = rol32(a, 5u) + f + e + k + w[i];
        e = d; d = c; c = rol32(b, 30u); b = a; a = temp;
    }
    context->state[0] += a; context->state[1] += b; context->state[2] += c; context->state[3] += d; context->state[4] += e;
}
static void sha1_update(sha1_context *context, const uint8_t *data, size_t length) {
    context->bytes += length;
    while (length != 0u) {
        size_t amount = sizeof(context->block) - context->used;
        if (amount > length) amount = length;
        memcpy(context->block + context->used, data, amount);
        context->used += amount; data += amount; length -= amount;
        if (context->used == sizeof(context->block)) { sha1_transform(context, context->block); context->used = 0u; }
    }
}
static void sha1_hex(const uint8_t *data, size_t length, char output[41]) {
    static const char digits[] = "0123456789abcdef";
    sha1_context context = {{0x67452301u, 0xefcdab89u, 0x98badcfeu, 0x10325476u, 0xc3d2e1f0u}, 0u, {0u}, 0u};
    sha1_update(&context, data, length);
    const uint64_t bits = context.bytes * 8u;
    const uint8_t marker = 0x80u; sha1_update(&context, &marker, 1u);
    const uint8_t zero = 0u;
    while (context.used != 56u) sha1_update(&context, &zero, 1u);
    uint8_t tail[8];
    for (size_t i = 0u; i < 8u; ++i) tail[7u - i] = (uint8_t)(bits >> (i * 8u));
    sha1_update(&context, tail, sizeof(tail));
    for (size_t i = 0u; i < 5u; ++i)
        for (size_t j = 0u; j < 4u; ++j) { const uint8_t byte = (uint8_t)(context.state[i] >> (24u - j * 8u)); *output++ = digits[byte >> 4]; *output++ = digits[byte & 15u]; }
    *output = '\0';
}

static uint16_t get16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void put32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}
static void put64(uint8_t *p, uint64_t v) {
    put32(p, (uint32_t)(v >> 32)); put32(p + 4, (uint32_t)v);
}
static int span(size_t total, uint32_t offset, size_t length) {
    return (size_t)offset <= total && length <= total - (size_t)offset;
}

static int zip_flags_valid(uint16_t flags, uint16_t method) {
    /* UTF-8 names are unnecessary for this ASCII profile. Permit only the
     * standard DEFLATE compression-level hints on DEFLATE entries. */
    if ((flags & (uint16_t)~UINT16_C(0x0806)) != 0u) return 0;
    return method == 8u || (flags & UINT16_C(0x0006)) == 0u;
}

static uint32_t role_for_name(const uint8_t *name, size_t length) {
    static const char *const names[ZIP_ENTRIES_MAX] = {
        "bios.bin", "program.bin", "fixed.bin", "audio.bin",
        "samples.bin", "sprites.bin"};
    for (uint32_t index = 0u; index < ZIP_ENTRIES_MAX; ++index) {
        if (strlen(names[index]) == length &&
            memcmp(name, names[index], length) == 0) return index + 1u;
    }
    return 0u;
}

static uint32_t expected_size(uint32_t role) {
    static const uint32_t sizes[ZIP_ENTRIES_MAX] = {
        0x80000u, 0x500000u, 0x20000u, 0x20000u, 0xa00000u, 0x3000000u};
    return role == 0u || role > ZIP_ENTRIES_MAX ? 0u : sizes[role - 1u];
}

static int safe_name(const uint8_t *name, size_t length) {
    if (length == 0u || length >= 64u) return 0;
    for (size_t i = 0u; i < length; ++i) {
        const uint8_t c = name[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) {
            return 0;
        }
    }
    return name[0] != '.';
}

static int extra_fields_valid(const uint8_t *extra, size_t length) {
    size_t cursor = 0u;
    while (cursor < length) {
        if (length - cursor < 4u) return IMPORT_MALFORMED;
        const uint16_t identifier = get16(extra + cursor);
        const uint16_t field_size = get16(extra + cursor + 2u);
        cursor += 4u;
        if (field_size > length - cursor) return IMPORT_MALFORMED;
        if (identifier == 1u) return IMPORT_UNSUPPORTED; /* ZIP64 */
        cursor += field_size;
    }
    return IMPORT_OK;
}

static int parse_candidate(const uint8_t *zip, size_t size, size_t eocd,
                           zip_entry entries[6], size_t *entry_count) {
    if (!span(size, (uint32_t)eocd, 22u)) return IMPORT_MALFORMED;
    const uint8_t *end = zip + eocd;
    const uint16_t comment = get16(end + 20u);
    if ((size_t)eocd + 22u + comment != size) return IMPORT_MALFORMED;
    if (get16(end + 4u) != 0u || get16(end + 6u) != 0u ||
        get16(end + 8u) != get16(end + 10u)) return IMPORT_UNSUPPORTED;
    const uint16_t count = get16(end + 10u);
    const uint32_t central_size = get32(end + 12u);
    const uint32_t central_offset = get32(end + 16u);
    if (count != ZIP_ENTRIES_MAX) return IMPORT_PROFILE;
    if (central_offset > eocd || central_size != eocd - central_offset ||
        !span(size, central_offset, central_size)) return IMPORT_MALFORMED;
    uint32_t seen = 0u;
    size_t compressed_total = 0u;
    size_t pos = central_offset;
    for (size_t i = 0u; i < count; ++i) {
        if (pos > size || size - pos < 46u || get32(zip + pos) != UINT32_C(0x02014b50))
            return IMPORT_MALFORMED;
        const uint8_t *record = zip + pos;
        const uint16_t flags = get16(record + 8u);
        const uint16_t method = get16(record + 10u);
        const uint32_t crc = get32(record + 16u);
        const uint32_t compressed = get32(record + 20u);
        const uint32_t expanded = get32(record + 24u);
        const uint16_t name_length = get16(record + 28u);
        const uint16_t extra_length = get16(record + 30u);
        const uint16_t comment_length = get16(record + 32u);
        const uint32_t disk = get16(record + 34u);
        const uint32_t local_offset = get32(record + 42u);
        const size_t rec_size = 46u + (size_t)name_length + extra_length + comment_length;
        if (!span(size, (uint32_t)pos, rec_size) || pos + rec_size > eocd) return IMPORT_MALFORMED;
        const uint8_t *name = record + 46u;
        if (!safe_name(name, name_length)) return IMPORT_UNSUPPORTED;
        const uint32_t role = role_for_name(name, name_length);
        if (role == 0u) return IMPORT_PROFILE;
        if ((seen & (UINT32_C(1) << role)) != 0u) return IMPORT_AMBIGUOUS;
        seen |= UINT32_C(1) << role;
        if (!zip_flags_valid(flags, method) || disk != 0u ||
            get32(record + 24u) == UINT32_MAX ||
            compressed == UINT32_MAX || method > 8u || (method != 0u && method != 8u))
            return IMPORT_UNSUPPORTED;
        if (expanded != expected_size(role) || expanded > REGION_MAX ||
            compressed > ZIP_INPUT_MAX) return IMPORT_LIMIT;
        if (compressed > ZIP_INPUT_MAX - compressed_total) return IMPORT_LIMIT;
        compressed_total += compressed;
        const int central_extra_status = extra_fields_valid(
            record + 46u + name_length, extra_length);
        if (central_extra_status != IMPORT_OK) return central_extra_status;
        if (!span(size, local_offset, 30u) || get32(zip + local_offset) != UINT32_C(0x04034b50))
            return IMPORT_MALFORMED;
        const uint8_t *local = zip + local_offset;
        const uint16_t local_flags = get16(local + 6u);
        const uint16_t local_method = get16(local + 8u);
        const uint16_t local_name_length = get16(local + 26u);
        const uint16_t local_extra_length = get16(local + 28u);
        const size_t local_variable_size = (size_t)local_name_length + local_extra_length;
        if (!span(size, local_offset + 30u, local_variable_size)) return IMPORT_MALFORMED;
        const size_t payload_size = (size_t)local_offset + 30u + local_variable_size;
        if (payload_size > UINT32_MAX) return IMPORT_MALFORMED;
        const uint32_t payload = (uint32_t)payload_size;
        const int local_extra_status = extra_fields_valid(
            local + 30u + local_name_length, local_extra_length);
        if (local_extra_status != IMPORT_OK) return local_extra_status;
        if (local_flags != flags || local_method != method ||
            local_name_length != name_length ||
            !span(size, local_offset + 30u, (size_t)local_name_length + local_extra_length) ||
            memcmp(local + 30u, name, name_length) != 0 ||
            get32(local + 14u) != crc || get32(local + 18u) != compressed ||
            get32(local + 22u) != expanded || !span(size, payload, compressed) ||
            payload + compressed > central_offset) return IMPORT_MALFORMED;
        zip_entry *entry = &entries[i];
        memset(entry, 0, sizeof(*entry));
        entry->role = role; entry->crc = crc; entry->compressed = compressed;
        entry->expanded = expanded; entry->method = method; entry->data_offset = payload;
        entry->extent_start = local_offset; entry->extent_end = payload + compressed;
        memcpy(entry->name, name, name_length); entry->name[name_length] = '\0';
        pos += rec_size;
    }
    if (pos != (size_t)central_offset + central_size || seen != UINT32_C(0x7e))
        return IMPORT_PROFILE;
    for (size_t i = 0u; i < count; ++i) {
        for (size_t j = i + 1u; j < count; ++j) {
            if (entries[i].extent_start < entries[j].extent_end &&
                entries[j].extent_start < entries[i].extent_end) return IMPORT_MALFORMED;
        }
    }
    *entry_count = count;
    return IMPORT_OK;
}

static int parse_zip(const uint8_t *zip, size_t size, zip_entry entries[6],
                     size_t *entry_count) {
    if (zip == NULL) return IMPORT_MALFORMED;
    if (size > ZIP_INPUT_MAX) return IMPORT_LIMIT;
    if (size < 22u) return IMPORT_MALFORMED;
    const size_t lower = size > 65557u ? size - 65557u : 0u;
    size_t valid_candidates = 0u;
    int last_status = IMPORT_MALFORMED;
    zip_entry candidate_entries[ZIP_ENTRIES_MAX];
    size_t candidate_count = 0u;
    for (size_t pos = size - 22u;; --pos) {
        if (get32(zip + pos) == UINT32_C(0x06054b50) &&
            (size_t)pos + 22u + get16(zip + pos + 20u) == size) {
            last_status = parse_candidate(zip, size, pos, candidate_entries,
                                          &candidate_count);
            if (last_status == IMPORT_OK) {
                ++valid_candidates;
                if (valid_candidates == 1u) {
                    memcpy(entries, candidate_entries,
                           candidate_count * sizeof(entries[0]));
                    *entry_count = candidate_count;
                }
            }
        }
        if (pos == lower) break;
    }
    if (valid_candidates > 1u) return IMPORT_AMBIGUOUS;
    return valid_candidates == 1u ? IMPORT_OK : last_status;
}

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size) {
    if (out_bundle == NULL || out_size == NULL) return IMPORT_MALFORMED;
    *out_bundle = NULL; *out_size = 0u;
    zip_entry entries[ZIP_ENTRIES_MAX];
    size_t count = 0u;
    int status = parse_zip(zip, zip_size, entries, &count);
    if (status != IMPORT_OK) return status;
    size_t output_size = BUNDLE_HEADER;
    for (size_t i = 0u; i < count; ++i) {
        if (output_size > OUTPUT_MAX - BUNDLE_ENTRY_HEADER ||
            entries[i].expanded > OUTPUT_MAX - output_size - BUNDLE_ENTRY_HEADER)
            return IMPORT_LIMIT;
        output_size += BUNDLE_ENTRY_HEADER + entries[i].expanded;
    }
    uint8_t *bundle = (uint8_t *)malloc(output_size);
    if (bundle == NULL) return IMPORT_MEMORY;
    memcpy(bundle, "GNMV", 4u); put32(bundle + 4u, 1u);
    put32(bundle + 8u, UINT32_C(0x4d53584d)); put32(bundle + 12u, (uint32_t)count);
    size_t cursor = BUNDLE_HEADER;
    for (uint32_t role = 1u; role <= ZIP_ENTRIES_MAX; ++role) {
        size_t found = count;
        for (size_t index = 0u; index < count; ++index)
            if (entries[index].role == role) found = index;
        if (found == count) { status = IMPORT_PROFILE; goto fail; }
        const zip_entry *entry = &entries[found];
        put32(bundle + cursor, role); put64(bundle + cursor + 4u, entry->expanded);
        cursor += BUNDLE_ENTRY_HEADER;
        if (entry->method == 0u) {
            if (entry->compressed != entry->expanded) { status = IMPORT_MALFORMED; goto fail; }
            memcpy(bundle + cursor, zip + entry->data_offset, entry->expanded);
        } else {
            z_stream stream;
            memset(&stream, 0, sizeof(stream));
            if (entry->compressed > UINT_MAX || entry->expanded > UINT_MAX ||
                inflateInit2(&stream, -MAX_WBITS) != Z_OK) {
                status = IMPORT_DECOMPRESS; goto fail;
            }
            stream.next_in = (Bytef *)(zip + entry->data_offset);
            stream.avail_in = entry->compressed;
            stream.next_out = bundle + cursor;
            stream.avail_out = entry->expanded;
            const int rc = inflate(&stream, Z_FINISH);
            const int valid = rc == Z_STREAM_END && stream.total_in == entry->compressed &&
                              stream.total_out == entry->expanded;
            (void)inflateEnd(&stream);
            if (!valid) { status = IMPORT_DECOMPRESS; goto fail; }
        }
        const uint32_t crc = (uint32_t)crc32(0L, bundle + cursor,
                                             (uInt)entry->expanded);
        if (crc != entry->crc) { status = IMPORT_DECOMPRESS; goto fail; }
        /* Normalize the word-swapped program ROM after validating its archive
         * CRC. The GNMV contract stores this region in bus order. */
        if (entry->role == 2u) {
            for (size_t byte = 0u; byte < entry->expanded; byte += 2u) {
                const uint8_t first = bundle[cursor + byte];
                bundle[cursor + byte] = bundle[cursor + byte + 1u];
                bundle[cursor + byte + 1u] = first;
            }
        }
        cursor += entry->expanded;
    }
    *out_bundle = bundle; *out_size = output_size;
    return IMPORT_OK;
fail:
    free(bundle);
    return status;
}

static const source_member *find_source(const char *name) {
    for (size_t i = 0u; i < sizeof(selected_sources) / sizeof(selected_sources[0]); ++i)
        if (strcmp(name, selected_sources[i].name) == 0) return &selected_sources[i];
    return NULL;
}

static int parse_source_zip(const uint8_t *zip, size_t size, int bios_archive,
                            zip_entry entries[SOURCE_ENTRIES_MAX], size_t *entry_count) {
    if (zip == NULL || size < 22u) return IMPORT_MALFORMED;
    if (size > SOURCE_ZIP_MAX) return IMPORT_LIMIT;
    const size_t lower = size > 65557u ? size - 65557u : 0u;
    size_t candidates = 0u;
    int candidate_status = IMPORT_MALFORMED;
    zip_entry accepted[SOURCE_ENTRIES_MAX]; size_t accepted_count = 0u;
    for (size_t eocd = size - 22u;; --eocd) {
        if (get32(zip + eocd) == UINT32_C(0x06054b50) &&
            eocd + 22u + get16(zip + eocd + 20u) == size) {
            const uint8_t *end = zip + eocd;
            const uint16_t count = get16(end + 10u);
            const uint32_t central_size = get32(end + 12u), central_offset = get32(end + 16u);
            if (get16(end + 4u) || get16(end + 6u) || get16(end + 8u) != count ||
                count == 0u || count > SOURCE_ENTRIES_MAX || central_offset > eocd ||
                central_size != eocd - central_offset) candidate_status = IMPORT_UNSUPPORTED;
            else {
                size_t pos = central_offset, found = 0u, expanded_total = 0u; int status = IMPORT_OK;
                zip_entry parsed[SOURCE_ENTRIES_MAX];
                for (size_t i = 0u; i < count && status == IMPORT_OK; ++i) {
                    if (!span(size, (uint32_t)pos, 46u) || get32(zip + pos) != UINT32_C(0x02014b50)) { status = IMPORT_MALFORMED; break; }
                    const uint8_t *record = zip + pos;
                    const uint16_t flags = get16(record + 8u), method = get16(record + 10u);
                    const uint16_t name_length = get16(record + 28u), extra_length = get16(record + 30u), comment_length = get16(record + 32u);
                    const size_t record_size = 46u + (size_t)name_length + extra_length + comment_length;
                    const uint32_t local_offset = get32(record + 42u), compressed = get32(record + 20u), expanded = get32(record + 24u);
                    if (!span(size, (uint32_t)pos, record_size) || pos + record_size > eocd ||
                        !safe_name(record + 46u, name_length) || name_length >= sizeof(parsed[0].name)) { status = IMPORT_MALFORMED; break; }
                    if (!zip_flags_valid(flags, method) || (method != 0u && method != 8u) ||
                        get16(record + 34u) != 0u || compressed == UINT32_MAX || expanded == UINT32_MAX) { status = IMPORT_UNSUPPORTED; break; }
                    if (expanded > 0x800000u || compressed > SOURCE_ZIP_MAX ||
                        extra_fields_valid(record + 46u + name_length, extra_length) != IMPORT_OK) { status = IMPORT_LIMIT; break; }
                    if (expanded > 128u * 1024u * 1024u - expanded_total) { status = IMPORT_LIMIT; break; }
                    expanded_total += expanded;
                    zip_entry *entry = &parsed[found]; memset(entry, 0, sizeof(*entry));
                    entry->crc = get32(record + 16u); entry->compressed = compressed; entry->expanded = expanded;
                    entry->method = method; entry->extent_start = local_offset;
                    memcpy(entry->name, record + 46u, name_length); entry->name[name_length] = '\0';
                    if (bios_archive) {
                        /* BIOS archives may carry unrelated flat members, but they
                         * remain untrusted input: metadata, extents, limits, and
                         * decompressed CRC are checked before they are ignored. */
                    } else if (find_source(entry->name) == NULL) { status = IMPORT_PROFILE; break; }
                    for (size_t prior = 0u; prior < found; ++prior)
                        if (strcmp(parsed[prior].name, entry->name) == 0) status = IMPORT_AMBIGUOUS;
                    if (status != IMPORT_OK) break;
                    if (!span(size, local_offset, 30u) || get32(zip + local_offset) != UINT32_C(0x04034b50)) { status = IMPORT_MALFORMED; break; }
                    const uint8_t *local = zip + local_offset;
                    const uint16_t local_name = get16(local + 26u), local_extra = get16(local + 28u);
                    if (get16(local + 6u) != flags || get16(local + 8u) != method || local_name != name_length ||
                        !span(size, local_offset + 30u, (size_t)local_name + local_extra) ||
                        memcmp(local + 30u, entry->name, name_length) != 0 ||
                        get32(local + 14u) != entry->crc || get32(local + 18u) != compressed ||
                        get32(local + 22u) != expanded ||
                        extra_fields_valid(local + 30u + local_name, local_extra) != IMPORT_OK) { status = IMPORT_MALFORMED; break; }
                    const size_t payload = (size_t)local_offset + 30u + local_name + local_extra;
                    if (payload > UINT32_MAX || !span(size, (uint32_t)payload, compressed) || payload + compressed > central_offset) { status = IMPORT_MALFORMED; break; }
                    entry->data_offset = (uint32_t)payload; entry->extent_end = (uint32_t)(payload + compressed);
                    ++found; pos += record_size;
                }
                if (status == IMPORT_OK && pos != (size_t)central_offset + central_size) status = IMPORT_MALFORMED;
                if (status == IMPORT_OK) {
                    for (size_t i = 0u; i < found; ++i)
                        for (size_t j = i + 1u; j < found; ++j)
                            if (parsed[i].extent_start < parsed[j].extent_end && parsed[j].extent_start < parsed[i].extent_end) status = IMPORT_MALFORMED;
                }
                candidate_status = status;
                if (status == IMPORT_OK) { ++candidates; memcpy(accepted, parsed, found * sizeof(parsed[0])); accepted_count = found; }
            }
        }
        if (eocd == lower) break;
    }
    if (candidates != 1u) return candidates > 1u ? IMPORT_AMBIGUOUS : candidate_status;
    memcpy(entries, accepted, accepted_count * sizeof(entries[0])); *entry_count = accepted_count;
    return IMPORT_OK;
}

static int source_expand(const uint8_t *zip, const zip_entry *entry, uint8_t *output) {
    if (entry->method == 0u) {
        if (entry->compressed != entry->expanded) return IMPORT_MALFORMED;
        memcpy(output, zip + entry->data_offset, entry->expanded);
    } else {
        z_stream stream; memset(&stream, 0, sizeof(stream));
        if (inflateInit2(&stream, -MAX_WBITS) != Z_OK) return IMPORT_DECOMPRESS;
        stream.next_in = (Bytef *)(zip + entry->data_offset); stream.avail_in = entry->compressed;
        stream.next_out = output; stream.avail_out = entry->expanded;
        const int rc = inflate(&stream, Z_FINISH);
        const int valid = rc == Z_STREAM_END && stream.total_in == entry->compressed && stream.total_out == entry->expanded;
        (void)inflateEnd(&stream);
        if (!valid) return IMPORT_DECOMPRESS;
    }
    return (uint32_t)crc32(0L, output, (uInt)entry->expanded) == entry->crc ? IMPORT_OK : IMPORT_DECOMPRESS;
}

int mvs_import_selected_memory(const uint8_t *game_zip, size_t game_size,
                               const uint8_t *bios_zip, size_t bios_size,
                               uint8_t **out_bundle, size_t *out_size) {
    if (out_bundle == NULL || out_size == NULL) return IMPORT_MALFORMED;
    *out_bundle = NULL; *out_size = 0u;
    if (game_size > SOURCE_ZIP_MAX || bios_size > SOURCE_ZIP_MAX || game_size > SIZE_MAX - bios_size ||
        game_size + bios_size > 128u * 1024u * 1024u) return IMPORT_LIMIT;
    zip_entry game[SOURCE_ENTRIES_MAX], bios[SOURCE_ENTRIES_MAX]; size_t game_count = 0u, bios_count = 0u;
    int status = parse_source_zip(game_zip, game_size, 0, game, &game_count);
    if (status != IMPORT_OK) return status;
    status = parse_source_zip(bios_zip, bios_size, 1, bios, &bios_count);
    if (status != IMPORT_OK) return status;
    if (game_count != sizeof(selected_sources) / sizeof(selected_sources[0])) return IMPORT_PROFILE;
    size_t selected_bios_count = 0u;
    for (size_t i = 0u; i < bios_count; ++i)
        if (strcmp(bios[i].name, selected_bios.name) == 0) ++selected_bios_count;
    if (selected_bios_count != 1u) return IMPORT_PROFILE;
    size_t expanded_total = 0u;
    for (size_t i = 0u; i < game_count; ++i) expanded_total += game[i].expanded;
    for (size_t i = 0u; i < bios_count; ++i) {
        if (bios[i].expanded > 128u * 1024u * 1024u - expanded_total) return IMPORT_LIMIT;
        expanded_total += bios[i].expanded;
    }
    const size_t output_size = BUNDLE_HEADER + 6u * BUNDLE_ENTRY_HEADER +
        expected_size(1u) + expected_size(2u) + expected_size(3u) + expected_size(4u) + expected_size(5u) + expected_size(6u);
    if (output_size > OUTPUT_MAX) return IMPORT_LIMIT;
    uint8_t *bundle = (uint8_t *)calloc(1u, output_size);
    if (bundle == NULL) return IMPORT_MEMORY;
    memcpy(bundle, "GNMV", 4u); put32(bundle + 4u, 1u); put32(bundle + 8u, UINT32_C(0x4d53584d)); put32(bundle + 12u, 6u);
    uint8_t *regions[7] = {NULL}; size_t cursor = BUNDLE_HEADER;
    for (uint32_t role = 1u; role <= 6u; ++role) {
        put32(bundle + cursor, role); put64(bundle + cursor + 4u, expected_size(role)); cursor += BUNDLE_ENTRY_HEADER;
        regions[role] = bundle + cursor; cursor += expected_size(role);
    }
    const zip_entry *bios_entry = NULL;
    for (size_t i = 0u; i < bios_count; ++i) if (strcmp(bios[i].name, "sp-s2.sp1") == 0) bios_entry = &bios[i];
    if (bios_entry == NULL || bios_entry->expanded != 0x20000u) { status = IMPORT_PROFILE; goto selected_fail; }
    uint8_t *temporary = (uint8_t *)malloc(0x800000u);
    if (temporary == NULL) { status = IMPORT_MEMORY; goto selected_fail; }
    for (size_t z = 0u; z < 2u; ++z) {
        zip_entry *entries = z == 0u ? game : bios; size_t count = z == 0u ? game_count : bios_count;
        const uint8_t *zip = z == 0u ? game_zip : bios_zip;
        for (size_t i = 0u; i < count; ++i) {
            status = source_expand(zip, &entries[i], temporary);
            if (status != IMPORT_OK) { free(temporary); goto selected_fail; }
            if (z == 1u && strcmp(entries[i].name, "sp-s2.sp1") != 0) continue;
            const source_member *member = z == 1u ? NULL : find_source(entries[i].name);
            if (z == 1u) {
#if !defined(MVS_IMPORT_TEST_IDENTITIES)
                char digest[41]; sha1_hex(temporary, entries[i].expanded, digest);
                if (entries[i].crc != selected_bios.crc || strcmp(digest, selected_bios.sha1) != 0) { free(temporary); status = IMPORT_PROFILE; goto selected_fail; }
#endif
                for (size_t j = 0u; j < 0x20000u; j += 2u) { regions[1][j] = temporary[j + 1u]; regions[1][j + 1u] = temporary[j]; }
                continue;
            }
            if (member == NULL || entries[i].expanded != member->size) { free(temporary); status = IMPORT_PROFILE; goto selected_fail; }
#if !defined(MVS_IMPORT_TEST_IDENTITIES)
            char digest[41]; sha1_hex(temporary, entries[i].expanded, digest);
            if (entries[i].crc != member->crc || strcmp(digest, member->sha1) != 0) { free(temporary); status = IMPORT_PROFILE; goto selected_fail; }
#endif
            uint8_t *destination = regions[member->role] + member->destination;
            if (member->transform == TRANSFORM_COPY) memcpy(destination, temporary, member->size);
            else if (member->transform == TRANSFORM_WORD_SWAP) {
                for (size_t j = 0u; j < member->size; j += 2u) { destination[j] = temporary[j + 1u]; destination[j + 1u] = temporary[j]; }
            } else {
                const size_t lane = member->transform == TRANSFORM_ODD ? 1u : 0u;
                for (size_t j = 0u; j < member->size; ++j) destination[j * 2u + lane] = temporary[j];
            }
        }
    }
    free(temporary);
    *out_bundle = bundle; *out_size = output_size;
    return IMPORT_OK;
selected_fail:
    free(bundle);
    return status;
}

#if !defined(MVS_IMPORT_NO_MAIN)
static const char *status_message(int status) {
    switch (status) {
        case IMPORT_MALFORMED: return "malformed ZIP32 media archive";
        case IMPORT_UNSUPPORTED: return "archive uses an unsupported ZIP feature";
        case IMPORT_LIMIT: return "media exceeds selected profile or resource limits";
        case IMPORT_PROFILE: return "required MVS profile regions are missing or incompatible";
        case IMPORT_DECOMPRESS: return "DEFLATE stream, expanded size, or CRC validation failed";
        case IMPORT_MEMORY: return "insufficient memory for bounded media import";
        case IMPORT_AMBIGUOUS: return "archive contains ambiguous MVS region entries";
        default: return "MVS media import failed";
    }
}

static int read_bounded(const char *path, uint8_t **bytes, size_t *length) {
    FILE *input = fopen(path, "rb");
    if (input == NULL) return 0;
    int ok = fseek(input, 0, SEEK_END) == 0;
    const long measured = ok ? ftell(input) : -1L;
    if (!ok || measured < 0 || (unsigned long)measured > SOURCE_ZIP_MAX ||
        fseek(input, 0, SEEK_SET) != 0) { fclose(input); return 0; }
    const size_t size = (size_t)measured;
    uint8_t *data = (uint8_t *)malloc(size == 0u ? 1u : size);
    if (data == NULL) { fclose(input); return 0; }
    const int read_ok = fread(data, 1u, size, input) == size;
    const int closed = fclose(input) == 0;
    if (!read_ok || !closed) {
        free(data); return 0;
    }
    *bytes = data; *length = size; return 1;
}

static int write_atomic(const char *path, const uint8_t *bytes, size_t length) {
    const size_t path_length = strlen(path);
    if (path_length > SIZE_MAX - 13u) return 0;
    char *temporary = (char *)malloc(path_length + 13u);
    if (temporary == NULL) return 0;
    memcpy(temporary, path, path_length); memcpy(temporary + path_length, ".tmp-XXXXXX", 12u);
#ifdef _WIN32
    if (_mktemp_s(temporary, path_length + 12u) != 0) { free(temporary); return 0; }
    const int descriptor = _open(temporary, _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY,
                                 _S_IREAD | _S_IWRITE);
    FILE *output = descriptor < 0 ? NULL : _fdopen(descriptor, "wb");
#else
    const int descriptor = mkstemp(temporary);
    FILE *output = descriptor < 0 ? NULL : fdopen(descriptor, "wb");
#endif
    if (output == NULL) {
#ifdef _WIN32
        if (descriptor >= 0) _close(descriptor);
#else
        if (descriptor >= 0) close(descriptor);
#endif
        free(temporary); return 0;
    }
    const int written = fwrite(bytes, 1u, length, output) == length;
    const int closed = fclose(output) == 0;
#ifdef _WIN32
    const int renamed = written && closed && MoveFileExA(temporary, path,
        MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
    const int renamed = written && closed && rename(temporary, path) == 0;
#endif
    if (!renamed) (void)remove(temporary);
    free(temporary);
    return renamed;
}

int main(int argc, char **argv) {
    if (argc == 5 && strcmp(argv[1], "--selected") == 0) {
        uint8_t *game = NULL, *bios = NULL, *bundle = NULL;
        size_t game_size = 0u, bios_size = 0u, bundle_size = 0u;
        if (!read_bounded(argv[2], &game, &game_size) || !read_bounded(argv[3], &bios, &bios_size)) {
            free(game); free(bios); fputs("selected media input could not be read within bounds\n", stderr); return 1;
        }
        const int status = mvs_import_selected_memory(game, game_size, bios, bios_size, &bundle, &bundle_size);
        free(game); free(bios);
        if (status != IMPORT_OK) { fprintf(stderr, "%s\n", status_message(status)); return status; }
        const int written = write_atomic(argv[4], bundle, bundle_size);
        free(bundle);
        if (!written) { fputs("normalized media could not be published atomically\n", stderr); return 1; }
        return 0;
    }
    if (argc != 3) { fputs("usage: mvs_importer input.zip output.gnmv\n", stderr); return 2; }
    FILE *input = fopen(argv[1], "rb");
    if (input == NULL) { fputs("input archive is unavailable\n", stderr); return 1; }
    if (fseek(input, 0, SEEK_END) != 0) {
        fclose(input); fputs("input archive could not be inspected\n", stderr); return 1;
    }
    const long length = ftell(input);
    if (length < 0 || (unsigned long)length > ZIP_INPUT_MAX || fseek(input, 0, SEEK_SET) != 0) {
        fclose(input); fputs("import input exceeds supported limit\n", stderr); return 1;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1u, (size_t)length, input) != (size_t)length) {
        free(bytes); fclose(input); fputs("import input could not be read\n", stderr); return 1;
    }
    fclose(input);
    uint8_t *bundle = NULL; size_t bundle_size = 0u;
    const int status = mvs_import_memory(bytes, (size_t)length, &bundle, &bundle_size);
    free(bytes);
    if (status != IMPORT_OK) {
        fprintf(stderr, "%s\n", status_message(status));
        return status;
    }
    FILE *output = fopen(argv[2], "wb");
    if (output == NULL) {
        free(bundle); fputs("normalized media could not be written\n", stderr); return 1;
    }
    const int written = fwrite(bundle, 1u, bundle_size, output) == bundle_size;
    const int closed = fclose(output) == 0;
    if (!written || !closed) {
        free(bundle); fputs("normalized media could not be written\n", stderr); return 1;
    }
    free(bundle);
    return 0;
}
#endif
