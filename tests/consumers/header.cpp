// SPDX-License-Identifier: MIT
#include <cstdio>

#include <glueyneo/glueyneo.h>

int main() {
    gn_instance *instance = nullptr;
    const gn_status status = gn_create(&instance);
    if (status != GN_STATUS_OK || instance == nullptr) {
        std::fprintf(stderr, "consumer C++ create failed: %s\n",
                     gn_status_string(status));
        gn_destroy(instance);
        return 1;
    }
    gn_destroy(instance);
    std::puts("SDK_CONSUMER_CPP {\"schema_version\":1,\"case_id\":\"sdk.consumer.cpp\",\"outcome\":\"pass\",\"assertions\":2}");
    return 0;
}
