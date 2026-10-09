/* SPDX-License-Identifier: MIT */
#include <zlib.h>

#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { IMPORT_OK, IMPORT_MALFORMED, IMPORT_UNSUPPORTED, IMPORT_LIMIT,
       IMPORT_PROFILE, IMPORT_DECOMPRESS, IMPORT_MEMORY };

#define ZIP_ENTRIES_MAX 6u
#define ZIP_INPUT_MAX (64u * 1024u * 1024u)
#define REGION_MAX (32u * 1024u * 1024u)
#define OUTPUT_MAX (48u * 1024u * 1024u)
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

static int parse_zip(const uint8_t *zip, size_t size, zip_entry entries[6],
                     size_t *entry_count) {
    if (zip == NULL || size < 22u || size > ZIP_INPUT_MAX) return IMPORT_LIMIT;
    size_t eocd = SIZE_MAX;
    const size_t lower = size > 65557u ? size - 65557u : 0u;
    for (size_t pos = size - 22u;; --pos) {
        if (get32(zip + pos) == UINT32_C(0x06054b50)) { eocd = pos; break; }
        if (pos == lower) break;
    }
    if (eocd == SIZE_MAX || !span(size, (uint32_t)eocd, 22u)) return IMPORT_MALFORMED;
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
        if ((seen & (UINT32_C(1) << role)) != 0u) return IMPORT_PROFILE;
        seen |= UINT32_C(1) << role;
        if (flags != 0u || disk != 0u || get32(record + 24u) == UINT32_MAX ||
            compressed == UINT32_MAX || method > 8u || (method != 0u && method != 8u))
            return IMPORT_UNSUPPORTED;
        if (expanded == 0u || expanded > REGION_MAX ||
            compressed > ZIP_INPUT_MAX) return IMPORT_LIMIT;
        if (!span(size, local_offset, 30u) || get32(zip + local_offset) != UINT32_C(0x04034b50))
            return IMPORT_MALFORMED;
        const uint8_t *local = zip + local_offset;
        const uint16_t local_flags = get16(local + 6u);
        const uint16_t local_method = get16(local + 8u);
        const uint16_t local_name_length = get16(local + 26u);
        const uint16_t local_extra_length = get16(local + 28u);
        const uint32_t payload = local_offset + 30u + local_name_length + local_extra_length;
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
        if (entries[i].expanded > OUTPUT_MAX - output_size - BUNDLE_ENTRY_HEADER)
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
        cursor += entry->expanded;
    }
    *out_bundle = bundle; *out_size = output_size;
    return IMPORT_OK;
fail:
    free(bundle);
    return status;
}

#if !defined(MVS_IMPORT_NO_MAIN)
int main(int argc, char **argv) {
    if (argc != 3) { fputs("usage: mvs_importer input.zip output.gnmv\n", stderr); return 2; }
    FILE *input = fopen(argv[1], "rb");
    if (input == NULL) { fputs("import input unavailable\n", stderr); return 1; }
    if (fseek(input, 0, SEEK_END) != 0) { fclose(input); return 1; }
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
    if (status != IMPORT_OK) { fputs("MVS archive rejected\n", stderr); return status; }
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
