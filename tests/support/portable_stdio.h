/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_PORTABLE_STDIO_H
#define GLUEYNEO_PORTABLE_STDIO_H

#include <stdio.h>

/* Keep source examples and host-side tools warning-clean with MSVC /W4 /WX. */
static inline FILE *gn_portable_fopen(const char *path, const char *mode) {
#if defined(_MSC_VER)
    FILE *file = NULL;
    if (fopen_s(&file, path, mode) != 0) return NULL;
    return file;
#else
    return fopen(path, mode);
#endif
}

#endif
