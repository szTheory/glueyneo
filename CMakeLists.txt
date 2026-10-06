cmake_minimum_required(VERSION 3.20)
project(Glueyneo LANGUAGES C)
include(CTest)

option(GLUEYNEO_BUILD_TESTS "Build SDK tests and the headless diagnostic" ${BUILD_TESTING})
option(GLUEYNEO_CPU_EXPERIMENT "Build the private CPU acceptance experiment" OFF)
option(GLUEYNEO_OWNED_CPU_EXPERIMENT "Build the private owned MC68000 experiment" OFF)
if(GLUEYNEO_CPU_EXPERIMENT AND GLUEYNEO_OWNED_CPU_EXPERIMENT)
  message(FATAL_ERROR "Select one whole CPU backend experiment per build directory")
endif()

add_library(glueyneo STATIC
  src/instance.c
  experiments/owned_cpu/cpu.c
)
add_library(Glueyneo::glueyneo ALIAS glueyneo)
target_compile_features(glueyneo PRIVATE c_std_17)
set_target_properties(glueyneo PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  C_VISIBILITY_PRESET hidden
)
target_include_directories(glueyneo
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
)
if(MSVC)
  target_compile_options(glueyneo PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
  execute_process(
    COMMAND git rev-parse --short=12 HEAD
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    OUTPUT_VARIABLE GLUEYNEO_SOURCE_REVISION
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
else()
  set(GLUEYNEO_SOURCE_REVISION "unknown")
endif()
if(NOT GLUEYNEO_SOURCE_REVISION)
  set(GLUEYNEO_SOURCE_REVISION "unknown")
endif()

add_executable(glueyneo-diagnostic tools/diagnostic/main.c)
target_compile_features(glueyneo-diagnostic PRIVATE c_std_17)
set_target_properties(glueyneo-diagnostic PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
)
target_link_libraries(glueyneo-diagnostic PRIVATE Glueyneo::glueyneo)
target_compile_definitions(glueyneo-diagnostic PRIVATE
  GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
  GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
  GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
  GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
)
if(MSVC)
  target_compile_options(glueyneo-diagnostic PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo-diagnostic PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

if(GLUEYNEO_BUILD_TESTS)
  enable_testing()
  add_library(glueyneo_unity STATIC third_party/unity/src/unity.c)
  target_include_directories(glueyneo_unity PUBLIC third_party/unity/src)
  target_compile_features(glueyneo_unity PRIVATE c_std_17)
  set_target_properties(glueyneo_unity PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  add_executable(sdk_diagnostic tests/sdk/test_sdk.c)
  target_compile_features(sdk_diagnostic PRIVATE c_std_17)
  set_target_properties(sdk_diagnostic PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_diagnostic PRIVATE Glueyneo::glueyneo glueyneo_unity)
  target_compile_definitions(sdk_diagnostic PRIVATE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
  )
  if(MSVC)
    target_compile_options(sdk_diagnostic PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_diagnostic PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME sdk_diagnostic COMMAND sdk_diagnostic)
  set_tests_properties(sdk_diagnostic PROPERTIES LABELS "sdk-contract;sdk-diagnostic")
  add_test(NAME sdk_provenance
    COMMAND glueyneo-diagnostic --check-fixture
            ${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original.bin)
  set_tests_properties(sdk_provenance PROPERTIES LABELS "sdk-provenance")
endif()

if(GLUEYNEO_CPU_EXPERIMENT)
  add_subdirectory(experiments/cpu)
endif()
if(GLUEYNEO_OWNED_CPU_EXPERIMENT)
  add_subdirectory(experiments/owned_cpu)
endif()
