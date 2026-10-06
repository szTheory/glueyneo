/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_SDK_PRIVATE_H
#define GLUEYNEO_SDK_PRIVATE_H

#include "glueyneo/glueyneo.h"

#if defined(GLUEYNEO_SDK_TEST_HOOKS)
gn_status gn_test_validate_region_layout(const gn_manifest *manifest);
gn_status gn_test_image_digest(const gn_instance *instance, uint64_t *out_digest);
#endif

#endif
