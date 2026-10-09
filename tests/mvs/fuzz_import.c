/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define MAX_INPUT ((size_t)64u * 1024u * 1024u)
#define MUTATIONS 48u

int mvs_import_memory(const uint8_t *zip, size_t zip_size,
                      uint8_t **out_bundle, size_t *out_size);

static void exercise(const uint8_t *bytes, size_t length) {
    uint8_t *bundle = NULL;
    size_t bundle_size = 0u;
    (void)mvs_import_memory(bytes, length, &bundle, &bundle_size);
    free(bundle);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) fclose(file);
        return 2;
    }
    const long size = ftell(file);
    if (size < 0 || (unsigned long)size > MAX_INPUT || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 2;
    }
    uint8_t *bytes = (uint8_t *)malloc((size_t)size);
    if (bytes == NULL || fread(bytes, 1u, (size_t)size, file) != (size_t)size) {
        free(bytes); fclose(file); return 2;
    }
    fclose(file);
    exercise(bytes, (size_t)size);
    uint32_t state = UINT32_C(0x51a7c0de);
    for (size_t iteration = 0u; iteration < MUTATIONS && size > 0; ++iteration) {
        state ^= state << 13; state ^= state >> 17; state ^= state << 5;
        const size_t offset = (size_t)state % (size_t)size;
        const uint8_t previous = bytes[offset];
        bytes[offset] ^= (uint8_t)(1u << (state & 7u));
        exercise(bytes, (size_t)size);
        bytes[offset] = previous;
    }
    free(bytes);
    return 0;
}
