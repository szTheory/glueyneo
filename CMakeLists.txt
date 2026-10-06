cmake_minimum_required(VERSION 3.20)
project(Glueyneo LANGUAGES C)
include(CTest)

option(GLUEYNEO_BUILD_TESTS "Build SDK tests and the headless diagnostic" ${BUILD_TESTING})
option(GLUEYNEO_CPU_EXPERIMENT "Build the private CPU acceptance experiment" OFF)
option(GLUEYNEO_OWNED_CPU_EXPERIMENT "Build the private owned MC68000 experiment" OFF)
if(GLUEYNEO_CPU_EXPERIMENT AND GLUEYNEO_OWNED_CPU_EXPERIMENT)
  message(FATAL_ERROR "Select one whole CPU backend experiment per build directory")
endif()

set(GLUEYNEO_RUNTIME_SOURCES
  src/instance.c
  experiments/owned_cpu/cpu.c
)
add_library(glueyneo STATIC ${GLUEYNEO_RUNTIME_SOURCES})
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

add_executable(glueyneo-diagnostic tools/diagnostic/main.c tests/sdk/guest_fixture.c)
target_include_directories(glueyneo-diagnostic PRIVATE tests/sdk)
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
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  find_package(Threads REQUIRED)
  add_library(glueyneo_test STATIC ${GLUEYNEO_RUNTIME_SOURCES})
  target_compile_features(glueyneo_test PRIVATE c_std_17)
  set_target_properties(glueyneo_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    C_VISIBILITY_PRESET hidden
  )
  target_include_directories(glueyneo_test
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/src
      ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
  )
  target_compile_definitions(glueyneo_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    OWNED_CPU_TEST_HOOKS
  )
  if(MSVC)
    target_compile_options(glueyneo_test PRIVATE /W4 /WX)
  else()
    target_compile_options(glueyneo_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()

  add_library(glueyneo_unity STATIC third_party/unity/src/unity.c)
  target_include_directories(glueyneo_unity PUBLIC third_party/unity/src)
  target_compile_features(glueyneo_unity PRIVATE c_std_17)
  set_target_properties(glueyneo_unity PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  add_executable(sdk_diagnostic tests/sdk/test_sdk.c tests/sdk/guest_fixture.c)
  target_include_directories(sdk_diagnostic PRIVATE tests/sdk src)
  target_compile_features(sdk_diagnostic PRIVATE c_std_17)
  set_target_properties(sdk_diagnostic PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_diagnostic PRIVATE
    glueyneo_test glueyneo_unity Threads::Threads)
  target_compile_definitions(sdk_diagnostic PRIVATE GLUEYNEO_SDK_TEST_HOOKS)
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
  add_test(NAME sdk_diagnostic COMMAND sdk_diagnostic diagnostic)
  set_tests_properties(sdk_diagnostic PROPERTIES LABELS "sdk-contract;sdk-diagnostic")
  add_test(NAME sdk_lifecycle COMMAND sdk_diagnostic lifecycle)
  set_tests_properties(sdk_lifecycle PROPERTIES LABELS "sdk-contract;sdk-lifecycle")
  add_test(NAME sdk_media COMMAND sdk_diagnostic media)
  set_tests_properties(sdk_media PROPERTIES LABELS "sdk-contract;sdk-media")
  add_test(NAME sdk_faults COMMAND sdk_diagnostic faults)
  set_tests_properties(sdk_faults PROPERTIES LABELS "sdk-contract;sdk-faults")
  add_test(NAME sdk_run COMMAND sdk_diagnostic run)
  set_tests_properties(sdk_run PROPERTIES LABELS "sdk-contract;sdk-run")
  add_test(NAME sdk_controls
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --controls
            $<TARGET_FILE:sdk_diagnostic> $<TARGET_FILE:glueyneo-diagnostic>)
  set_tests_properties(sdk_controls PROPERTIES LABELS "sdk-controls")
  add_test(NAME sdk_isolation
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --isolation
            $<TARGET_FILE:sdk_diagnostic>)
  add_test(NAME sdk_cold
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --cold
            $<TARGET_FILE:sdk_diagnostic>)
  set_tests_properties(sdk_isolation sdk_cold PROPERTIES
    LABELS "sdk-isolation" TIMEOUT 180)

  # Keep the runtime source closure explicit, then inspect both source and the
  # linked target for ambient host services used by the native core.
  set(SDK_HOST_CLOSURE_SCRIPT "${CMAKE_CURRENT_BINARY_DIR}/sdk-host-closure.cmake")
  set(SDK_RUNTIME_ABSOLUTE_SOURCES)
  foreach(runtime_source IN LISTS GLUEYNEO_RUNTIME_SOURCES)
    list(APPEND SDK_RUNTIME_ABSOLUTE_SOURCES
      "${CMAKE_CURRENT_SOURCE_DIR}/${runtime_source}")
  endforeach()
  set(SDK_HOST_CLOSURE_CONTENT [=[
set(_sdk_sources "@SDK_RUNTIME_ABSOLUTE_SOURCES@")
set(_sdk_library "$<TARGET_FILE:glueyneo>")
set(_sdk_nm "@CMAKE_NM@")
set(_sdk_host_calls "(^|[^A-Za-z0-9_])(fopen|freopen|fread|fwrite|remove|rename|open|close|read|write|time|clock|gettimeofday|socket|connect|accept|system|fork|execve|pthread_create|pthread_mutex_lock)[ \t]*\\(")
foreach(_sdk_source IN LISTS _sdk_sources)
  file(READ "${_sdk_source}" _sdk_text)
  if(_sdk_text MATCHES "${_sdk_host_calls}")
    message(FATAL_ERROR "Ambient host call found in runtime source: ${_sdk_source}")
  endif()
endforeach()
execute_process(COMMAND "${_sdk_nm}" -u "${_sdk_library}"
  RESULT_VARIABLE _sdk_nm_result OUTPUT_VARIABLE _sdk_symbols ERROR_VARIABLE _sdk_nm_error)
if(NOT _sdk_nm_result EQUAL 0)
  message(FATAL_ERROR "Could not inspect runtime symbols: ${_sdk_nm_error}")
endif()
if(_sdk_symbols MATCHES "(^|[^A-Za-z0-9_])_?(fopen|freopen|fread|fwrite|remove|rename|open|close|read|write|time|clock|gettimeofday|socket|connect|accept|system|fork|execve|pthread_create|pthread_mutex_lock)($|[^A-Za-z0-9_])")
  message(FATAL_ERROR "Ambient host symbol found in runtime: ${_sdk_symbols}")
endif()
execute_process(COMMAND "${_sdk_nm}" -g "${_sdk_library}"
  RESULT_VARIABLE _sdk_global_nm_result OUTPUT_VARIABLE _sdk_global_symbols
  ERROR_VARIABLE _sdk_global_nm_error)
if(NOT _sdk_global_nm_result EQUAL 0)
  message(FATAL_ERROR "Could not inspect runtime exports: ${_sdk_global_nm_error}")
endif()
if(_sdk_global_symbols MATCHES "gn_test_")
  message(FATAL_ERROR "Private test hook leaked into public runtime: ${_sdk_global_symbols}")
endif()
message(STATUS "SDK runtime host-call closure passed for ${_sdk_library}")
]=])
  string(CONFIGURE "${SDK_HOST_CLOSURE_CONTENT}" SDK_HOST_CLOSURE_CONTENT @ONLY)
  file(GENERATE OUTPUT "${SDK_HOST_CLOSURE_SCRIPT}" CONTENT "${SDK_HOST_CLOSURE_CONTENT}")
  add_test(NAME sdk_host_closure COMMAND ${CMAKE_COMMAND} -P "${SDK_HOST_CLOSURE_SCRIPT}")
  set_tests_properties(sdk_host_closure PROPERTIES LABELS "sdk-lifecycle;sdk-capabilities")
  add_test(NAME sdk_fixture_write
    COMMAND glueyneo-diagnostic --write-fixture
            ${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin)
  set_tests_properties(sdk_fixture_write PROPERTIES
    FIXTURES_SETUP sdk_fixture_a
    LABELS "sdk-provenance"
  )
  add_test(NAME sdk_provenance
    COMMAND glueyneo-diagnostic --check-fixture
            ${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin)
  set_tests_properties(sdk_provenance PROPERTIES
    FIXTURES_REQUIRED sdk_fixture_a
    LABELS "sdk-provenance"
  )
endif()

if(GLUEYNEO_CPU_EXPERIMENT)
  add_subdirectory(experiments/cpu)
endif()
if(GLUEYNEO_OWNED_CPU_EXPERIMENT)
  add_subdirectory(experiments/owned_cpu)
endif()
