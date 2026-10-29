# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.20)
project(GlueyneoInstalledConsumer LANGUAGES C CXX)

# Keep the guide's documented ./build/examples-*/ executable paths stable
# across single- and multi-configuration generators. A generator expression
# prevents multi-config generators from appending a config-specific directory.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/$<0:>")

# Standalone SDK examples carry the same manifest as their source release.
# In the source checkout, use the root manifest directly.
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

# The sanitizer export control stages this separate C++17 loaded-media
# consumer; generic package/docs projects may stage only the header smoke.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/sanitizer_runtime.cpp")
  add_executable(glueyneo-installed-cxx-runtime sanitizer_runtime.cpp)
  target_link_libraries(glueyneo-installed-cxx-runtime PRIVATE Glueyneo::glueyneo)
  target_compile_features(glueyneo-installed-cxx-runtime PRIVATE cxx_std_17)
  set_target_properties(glueyneo-installed-cxx-runtime PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
  )
endif()

if(NOT DEFINED GLUEYNEO_SOUND_FIXTURE_SOURCE)
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/public_sound_guest.c")
    set(GLUEYNEO_SOUND_FIXTURE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/public_sound_guest.c")
  else()
    set(GLUEYNEO_SOUND_FIXTURE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/../fixture/public_sound_guest.c")
  endif()
endif()
add_executable(glueyneo-installed-sound sound_consumer.c "${GLUEYNEO_SOUND_FIXTURE_SOURCE}")
target_link_libraries(glueyneo-installed-sound PRIVATE Glueyneo::glueyneo)
set_target_properties(glueyneo-installed-sound PROPERTIES
  C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)

set(_continuation_source "${CMAKE_CURRENT_SOURCE_DIR}/continuation.c")
if(NOT EXISTS "${_continuation_source}")
  set(_continuation_source "${CMAKE_CURRENT_LIST_DIR}/../../examples/continuation.c")
endif()
if(EXISTS "${_continuation_source}")
  add_executable(glueyneo-installed-continuation "${_continuation_source}")
  target_link_libraries(glueyneo-installed-continuation PRIVATE Glueyneo::glueyneo)
  target_compile_features(glueyneo-installed-continuation PRIVATE c_std_17)
  set_target_properties(glueyneo-installed-continuation PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
endif()

set(_persistence_source "${CMAKE_CURRENT_SOURCE_DIR}/persistence.c")
set(_persistence_host_source "${CMAKE_CURRENT_SOURCE_DIR}/persistence_host.c")
set(_persistence_guest_source "${CMAKE_CURRENT_SOURCE_DIR}/public_persistence_guest.c")
if(NOT EXISTS "${_persistence_source}")
  set(_persistence_source "${CMAKE_CURRENT_LIST_DIR}/../../examples/persistence.c")
endif()
if(NOT EXISTS "${_persistence_host_source}")
  set(_persistence_host_source "${CMAKE_CURRENT_LIST_DIR}/../../examples/persistence_host.c")
endif()
if(NOT EXISTS "${_persistence_guest_source}")
  set(_persistence_guest_source "${CMAKE_CURRENT_LIST_DIR}/../fixture/public_persistence_guest.c")
endif()
if(EXISTS "${_persistence_source}" AND
   EXISTS "${_persistence_host_source}" AND
   EXISTS "${_persistence_guest_source}")
  add_executable(glueyneo-installed-persistence
    "${_persistence_source}" "${_persistence_host_source}"
    "${_persistence_guest_source}" "${GLUEYNEO_SOUND_FIXTURE_SOURCE}")
  target_link_libraries(glueyneo-installed-persistence PRIVATE Glueyneo::glueyneo)
  target_compile_features(glueyneo-installed-persistence PRIVATE c_std_17)
  set_target_properties(glueyneo-installed-persistence PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)

  add_executable(glueyneo-installed-persistence-faults
    "${_persistence_source}" "${_persistence_host_source}"
    "${_persistence_guest_source}" "${GLUEYNEO_SOUND_FIXTURE_SOURCE}")
  target_link_libraries(glueyneo-installed-persistence-faults PRIVATE Glueyneo::glueyneo)
  target_compile_features(glueyneo-installed-persistence-faults PRIVATE c_std_17)
  target_compile_definitions(glueyneo-installed-persistence-faults PRIVATE
    GLUEYNEO_PERSISTENCE_TESTING=1)
  set_target_properties(glueyneo-installed-persistence-faults PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
endif()
