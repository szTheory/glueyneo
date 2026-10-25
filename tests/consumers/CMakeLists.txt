# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.20)
project(GlueyneoInstalledConsumer LANGUAGES C CXX)

# The source consumer reads the root manifest; the packaged example carries a
# staged copy beside this file. Both keep exact matching after release bumps.
set(_manifest "${CMAKE_CURRENT_LIST_DIR}/.release-please-manifest.json")
if(NOT EXISTS "${_manifest}")
  set(_manifest "${CMAKE_CURRENT_LIST_DIR}/../../.release-please-manifest.json")
endif()
file(READ "${_manifest}" _manifest_json)
string(JSON GLUEYNEO_CONSUMER_VERSION GET "${_manifest_json}" ".")
find_package(Glueyneo "${GLUEYNEO_CONSUMER_VERSION}" EXACT CONFIG REQUIRED)

add_executable(glueyneo-installed-c "${GLUEYNEO_CONSUMER_C_SOURCE}")
target_link_libraries(glueyneo-installed-c PRIVATE Glueyneo::glueyneo)
target_compile_features(glueyneo-installed-c PRIVATE c_std_17)
set_target_properties(glueyneo-installed-c PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
)

add_executable(glueyneo-installed-cxx header.cpp)
target_link_libraries(glueyneo-installed-cxx PRIVATE Glueyneo::glueyneo)
target_compile_features(glueyneo-installed-cxx PRIVATE cxx_std_17)
set_target_properties(glueyneo-installed-cxx PROPERTIES
  CXX_STANDARD 17
  CXX_STANDARD_REQUIRED YES
  CXX_EXTENSIONS NO
)
