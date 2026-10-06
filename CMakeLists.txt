cmake_minimum_required(VERSION 3.20)

# release-please owns the only project version. Keep this parsing before
# project() so CMake's installed package version uses the manifest value.
set(GLUEYNEO_RELEASE_MANIFEST "${CMAKE_CURRENT_LIST_DIR}/.release-please-manifest.json")
if(NOT EXISTS "${GLUEYNEO_RELEASE_MANIFEST}")
  message(FATAL_ERROR "release-please manifest is missing: ${GLUEYNEO_RELEASE_MANIFEST}")
endif()
file(READ "${GLUEYNEO_RELEASE_MANIFEST}" GLUEYNEO_RELEASE_MANIFEST_JSON)
string(JSON GLUEYNEO_RELEASE_MANIFEST_LENGTH ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       LENGTH "${GLUEYNEO_RELEASE_MANIFEST_JSON}")
if(GLUEYNEO_RELEASE_JSON_ERROR OR NOT GLUEYNEO_RELEASE_MANIFEST_LENGTH EQUAL 1)
  message(FATAL_ERROR "release-please manifest must be a valid object containing only the root package")
endif()
string(JSON GLUEYNEO_RELEASE_MANIFEST_PACKAGE ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       MEMBER "${GLUEYNEO_RELEASE_MANIFEST_JSON}" 0)
if(GLUEYNEO_RELEASE_JSON_ERROR OR NOT GLUEYNEO_RELEASE_MANIFEST_PACKAGE STREQUAL ".")
  message(FATAL_ERROR "release-please manifest must define exactly the root package key '.'")
endif()
string(JSON GLUEYNEO_PROJECT_VERSION ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       GET "${GLUEYNEO_RELEASE_MANIFEST_JSON}" ".")
if(GLUEYNEO_RELEASE_JSON_ERROR OR
   NOT GLUEYNEO_PROJECT_VERSION MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?(\\+[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$")
  message(FATAL_ERROR "release-please manifest root version must be valid semantic version text")
endif()

project(Glueyneo VERSION "${GLUEYNEO_PROJECT_VERSION}" LANGUAGES C)
include(CTest)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

option(GLUEYNEO_BUILD_TESTS "Build SDK tests and the headless diagnostic" ${BUILD_TESTING})
option(GLUEYNEO_CPU_EXPERIMENT "Build the private CPU acceptance experiment" OFF)
option(GLUEYNEO_OWNED_CPU_EXPERIMENT "Build the private owned MC68000 experiment" OFF)
set(GLUEYNEO_SDK_SANITIZER "NONE" CACHE STRING
    "SDK-only instrumentation: NONE, ADDRESS_UNDEFINED, or THREAD")
set_property(CACHE GLUEYNEO_SDK_SANITIZER PROPERTY STRINGS
             NONE ADDRESS_UNDEFINED THREAD)
if(NOT GLUEYNEO_SDK_SANITIZER MATCHES "^(NONE|ADDRESS_UNDEFINED|THREAD)$")
  message(FATAL_ERROR "Unknown SDK sanitizer mode: ${GLUEYNEO_SDK_SANITIZER}")
endif()

set(GLUEYNEO_SDK_SANITIZER_FLAGS "")
set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS "")
if(GLUEYNEO_SDK_SANITIZER STREQUAL "ADDRESS_UNDEFINED")
  include(CheckCCompilerFlag)
  include(CheckLinkerFlag)
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=address,undefined")
  check_c_compiler_flag("-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_COMPILE)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  check_linker_flag(C "-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_LINK)
  if(NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_COMPILE OR
     NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_LINK)
    message(FATAL_ERROR
      "SDK_SANITIZER_UNSUPPORTED: selected C compiler/linker lacks ASan+UBSan")
  endif()
  set(GLUEYNEO_SDK_SANITIZER_FLAGS
      -fsanitize=address,undefined -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS
      -fsanitize=address,undefined -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
elseif(GLUEYNEO_SDK_SANITIZER STREQUAL "THREAD")
  include(CheckCCompilerFlag)
  include(CheckLinkerFlag)
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=thread")
  check_c_compiler_flag("-fsanitize=thread"
    GLUEYNEO_SDK_HAS_TSAN_COMPILE)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  check_linker_flag(C "-fsanitize=thread" GLUEYNEO_SDK_HAS_TSAN_LINK)
  if(NOT GLUEYNEO_SDK_HAS_TSAN_COMPILE OR NOT GLUEYNEO_SDK_HAS_TSAN_LINK)
    message(FATAL_ERROR
      "SDK_SANITIZER_UNSUPPORTED: selected C compiler/linker lacks TSan")
  endif()
  set(GLUEYNEO_SDK_SANITIZER_FLAGS
      -fsanitize=thread -fno-omit-frame-pointer -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS
      -fsanitize=thread -fno-omit-frame-pointer -fno-sanitize-recover=all)
endif()

function(glueyneo_apply_sdk_sanitizer target)
  if(GLUEYNEO_SDK_SANITIZER_FLAGS)
    target_compile_options(${target} PRIVATE ${GLUEYNEO_SDK_SANITIZER_FLAGS})
    get_target_property(target_type ${target} TYPE)
    if(NOT target_type STREQUAL "STATIC_LIBRARY")
      target_link_options(${target} PRIVATE ${GLUEYNEO_SDK_SANITIZER_LINK_FLAGS})
    endif()
  endif()
endfunction()

if(GLUEYNEO_CPU_EXPERIMENT AND GLUEYNEO_OWNED_CPU_EXPERIMENT)
  message(FATAL_ERROR "Select one whole CPU backend experiment per build directory")
endif()

set(GLUEYNEO_RUNTIME_SOURCES
  src/instance.c
  experiments/owned_cpu/cpu.c
)
add_library(glueyneo ${GLUEYNEO_RUNTIME_SOURCES})
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
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
)
if(BUILD_SHARED_LIBS)
  target_compile_definitions(glueyneo
    PUBLIC GLUEYNEO_SHARED
    PRIVATE GLUEYNEO_BUILDING
  )
endif()
if(MSVC)
  target_compile_options(glueyneo PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
glueyneo_apply_sdk_sanitizer(glueyneo)

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
glueyneo_apply_sdk_sanitizer(glueyneo-diagnostic)

if(APPLE)
  set_target_properties(glueyneo-diagnostic PROPERTIES
    INSTALL_RPATH "@loader_path/../${CMAKE_INSTALL_LIBDIR}"
  )
elseif(UNIX)
  set_target_properties(glueyneo-diagnostic PROPERTIES
    INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}"
  )
endif()

set(GLUEYNEO_DIAGNOSTIC_FIXTURE
  "${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin")
add_custom_command(
  OUTPUT "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  COMMAND $<TARGET_FILE:glueyneo-diagnostic> --write-fixture
          "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DEPENDS glueyneo-diagnostic
  VERBATIM
)
add_custom_target(glueyneo-original-fixture ALL
  DEPENDS "${GLUEYNEO_DIAGNOSTIC_FIXTURE}")

install(TARGETS glueyneo
  EXPORT GlueyneoTargets
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(TARGETS glueyneo-diagnostic
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
)
install(DIRECTORY include/glueyneo
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(FILES LICENSE DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo")
install(FILES "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/glueyneo")

set(GLUEYNEO_CMAKE_INSTALL_DIR "${CMAKE_INSTALL_LIBDIR}/cmake/Glueyneo")
configure_package_config_file(
  cmake/GlueyneoConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfig.cmake"
  INSTALL_DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)
install(EXPORT GlueyneoTargets
  FILE GlueyneoTargets.cmake
  NAMESPACE Glueyneo::
  DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)
install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfigVersion.cmake"
  DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)

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
  glueyneo_apply_sdk_sanitizer(glueyneo_test)

  add_library(glueyneo_unity STATIC third_party/unity/src/unity.c)
  target_include_directories(glueyneo_unity PUBLIC third_party/unity/src)
  target_compile_features(glueyneo_unity PRIVATE c_std_17)
  set_target_properties(glueyneo_unity PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  glueyneo_apply_sdk_sanitizer(glueyneo_unity)
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
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_diagnostic PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_diagnostic PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_diagnostic)
  add_executable(sdk_mutation
    tests/fuzz/sdk_mutation.c
    tests/sdk/guest_fixture.c
  )
  target_include_directories(sdk_mutation PRIVATE tests/sdk)
  target_compile_features(sdk_mutation PRIVATE c_std_17)
  set_target_properties(sdk_mutation PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_mutation PRIVATE glueyneo glueyneo_unity Threads::Threads)
  target_compile_definitions(sdk_mutation PRIVATE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_mutation PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_mutation PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_mutation)
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
  add_test(NAME sdk_mutation_media COMMAND sdk_mutation --media)
  add_test(NAME sdk_mutation_sequence COMMAND sdk_mutation --sequence)
  add_test(NAME sdk_mutation_minimizer
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/fuzz/minimize.py
            --self-test)
  set_tests_properties(sdk_mutation_media sdk_mutation_sequence
    sdk_mutation_minimizer PROPERTIES LABELS "sdk-hostile;sdk-mutation" TIMEOUT 180)
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

  set(GLUEYNEO_CONSUMER_CHECK
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/check_package.py")
  add_test(NAME sdk_package_build_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case build-static)
  add_test(NAME sdk_package_build_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case build-shared)
  add_test(NAME sdk_package_consumers_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case consumers-static)
  add_test(NAME sdk_package_consumers_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case consumers-shared)
  add_test(NAME sdk_package_docs_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-static)
  add_test(NAME sdk_package_docs_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-shared)
  add_test(NAME sdk_package_docs_readme
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-readme)
  add_test(NAME sdk_package_capabilities
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case capabilities)
  set_tests_properties(sdk_package_build_static sdk_package_build_shared
    PROPERTIES LABELS "sdk-package-build" TIMEOUT 360)
  set_tests_properties(sdk_package_consumers_static sdk_package_consumers_shared
    PROPERTIES LABELS "sdk-package-consumers" TIMEOUT 360)
  set_tests_properties(sdk_package_docs_static sdk_package_docs_shared sdk_package_docs_readme
    PROPERTIES LABELS "sdk-package-docs" TIMEOUT 600)
  set_tests_properties(sdk_package_capabilities
    PROPERTIES LABELS "sdk-package-capabilities" TIMEOUT 180)
endif()

if(GLUEYNEO_CPU_EXPERIMENT)
  add_subdirectory(experiments/cpu)
endif()
if(GLUEYNEO_OWNED_CPU_EXPERIMENT)
  add_subdirectory(experiments/owned_cpu)
endif()
