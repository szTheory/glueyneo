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

# ZIP handling is isolated to the standalone importer. These exact upstream
# zlib 1.3.2 inflater/CRC sources are pinned at da607da739fa6047df13e66a2af6b8bec7c2a498.
add_library(glueyneo_mvs_zlib STATIC
  third_party/zlib/adler32.c
  third_party/zlib/crc32.c
  third_party/zlib/inflate.c
  third_party/zlib/inffast.c
  third_party/zlib/inftrees.c
  third_party/zlib/zutil.c
)
target_include_directories(glueyneo_mvs_zlib PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/zlib)
target_compile_features(glueyneo_mvs_zlib PRIVATE c_std_17)
set_target_properties(glueyneo_mvs_zlib PROPERTIES C_STANDARD 17
  C_STANDARD_REQUIRED YES C_EXTENSIONS NO POSITION_INDEPENDENT_CODE ON)

option(GLUEYNEO_BUILD_TESTS "Build SDK tests and the headless diagnostic" ${BUILD_TESTING})
option(GLUEYNEO_YM2610_ADMISSION "Build the private ymfm YM2610 admission candidate" ${GLUEYNEO_BUILD_TESTS})
option(GLUEYNEO_CPU_EXPERIMENT "Build the private CPU acceptance experiment" OFF)
option(GLUEYNEO_OWNED_CPU_EXPERIMENT "Build the private owned MC68000 experiment" OFF)
set(GLUEYNEO_SDK_SANITIZER "NONE" CACHE STRING
    "SDK-only instrumentation: NONE, ADDRESS_UNDEFINED, or THREAD")
set_property(CACHE GLUEYNEO_SDK_SANITIZER PROPERTY STRINGS
             NONE ADDRESS_UNDEFINED THREAD)
if(NOT GLUEYNEO_SDK_SANITIZER MATCHES "^(NONE|ADDRESS_UNDEFINED|THREAD)$")
  message(FATAL_ERROR "Unknown SDK sanitizer mode: ${GLUEYNEO_SDK_SANITIZER}")
endif()

if(GLUEYNEO_YM2610_ADMISSION)
  enable_language(CXX)
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

glueyneo_apply_sdk_sanitizer(glueyneo_mvs_zlib)

if(GLUEYNEO_CPU_EXPERIMENT AND GLUEYNEO_OWNED_CPU_EXPERIMENT)
  message(FATAL_ERROR "Select one whole CPU backend experiment per build directory")
endif()

set(GLUEYNEO_RUNTIME_SOURCES
  src/instance.c
  src/mvs/mvs_bus.c
  experiments/owned_cpu/cpu.c
)
add_library(glueyneo ${GLUEYNEO_RUNTIME_SOURCES})
add_library(Glueyneo::glueyneo ALIAS glueyneo)
target_compile_features(glueyneo PRIVATE c_std_17)
set_target_properties(glueyneo PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  POSITION_INDEPENDENT_CODE ON
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

# The frontend adapter owns the Libretro ABI boundary; machine behavior and
# deterministic frame buffers remain in the native C library.
add_library(glueyneo_libretro SHARED src/libretro/libretro_core.c)
target_compile_features(glueyneo_libretro PRIVATE c_std_17)
set_target_properties(glueyneo_libretro PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  C_VISIBILITY_PRESET hidden
  OUTPUT_NAME glueyneo_libretro
  PREFIX ""
)
target_include_directories(glueyneo_libretro PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/libretro
)
target_link_libraries(glueyneo_libretro PRIVATE Glueyneo::glueyneo)
install(TARGETS glueyneo_libretro
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/libretro"
  RUNTIME DESTINATION "${CMAKE_INSTALL_LIBDIR}/libretro"
)
if(MSVC)
  target_compile_options(glueyneo_libretro PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo_libretro PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
glueyneo_apply_sdk_sanitizer(glueyneo_libretro)

# Source identity belongs to the checkout, independently of the C compiler.
# An offline source archive without Git retains the explicit unknown identity.
execute_process(
  COMMAND git rev-parse --short=12 HEAD
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  RESULT_VARIABLE GLUEYNEO_SOURCE_REVISION_RESULT
  OUTPUT_VARIABLE GLUEYNEO_SOURCE_REVISION
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET
)
if(NOT GLUEYNEO_SOURCE_REVISION_RESULT EQUAL 0 OR NOT GLUEYNEO_SOURCE_REVISION)
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
if(GLUEYNEO_YM2610_ADMISSION)
  add_library(glueyneo_ym2610_candidate
    src/chips/ym2610_candidate.cpp
    third_party/ymfm/src/ymfm_opn.cpp
    third_party/ymfm/src/ymfm_adpcm.cpp
    third_party/ymfm/src/ymfm_ssg.cpp
  )
  add_library(Glueyneo::ym2610_candidate ALIAS glueyneo_ym2610_candidate)
  target_compile_features(glueyneo_ym2610_candidate PUBLIC c_std_17 PRIVATE cxx_std_14)
  set_target_properties(glueyneo_ym2610_candidate PROPERTIES
    EXPORT_NAME ym2610_candidate
    CXX_STANDARD 14
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
    POSITION_INDEPENDENT_CODE ON
  )
  target_include_directories(glueyneo_ym2610_candidate
    PUBLIC
      $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/chips>
      $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/glueyneo/private>
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/third_party/ymfm/src
  )
  target_compile_definitions(glueyneo_ym2610_candidate
    PUBLIC GLUEYNEO_YM2610_TEST_HOOKS
    PRIVATE GLUEYNEO_YM2610_CANDIDATE_BUILD
  )
  if(BUILD_SHARED_LIBS AND WIN32)
    target_compile_definitions(glueyneo_ym2610_candidate
      INTERFACE GLUEYNEO_YM2610_CANDIDATE_SHARED
    )
  endif()
  if(APPLE)
    target_link_libraries(glueyneo_ym2610_candidate INTERFACE
      "$<$<LINK_LANGUAGE:C>:c++>"
    )
  elseif(UNIX)
    target_link_libraries(glueyneo_ym2610_candidate INTERFACE
      "$<$<LINK_LANGUAGE:C>:stdc++>"
    )
  endif()
  if(MSVC)
    target_compile_options(glueyneo_ym2610_candidate PRIVATE /W4)
  else()
    target_compile_options(glueyneo_ym2610_candidate PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  install(TARGETS glueyneo_ym2610_candidate
    EXPORT GlueyneoTargets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
    INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  )
  install(FILES src/chips/ym2610_candidate.h
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/glueyneo/private"
  )
endif()
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
  if(NOT WIN32)
    find_package(Threads REQUIRED)
  endif()
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

  if(GLUEYNEO_YM2610_ADMISSION)
    add_executable(ym2610_admission_test tests/chips/test_ym2610.c)
    target_include_directories(ym2610_admission_test PRIVATE src/chips)
    target_compile_features(ym2610_admission_test PRIVATE c_std_17)
    set_target_properties(ym2610_admission_test PROPERTIES
      C_STANDARD 17
      C_STANDARD_REQUIRED YES
      C_EXTENSIONS NO
    )
    target_compile_definitions(ym2610_admission_test PRIVATE GLUEYNEO_YM2610_TEST_HOOKS)
    target_link_libraries(ym2610_admission_test PRIVATE
      glueyneo_ym2610_candidate glueyneo_unity
    )
    if(MSVC)
      target_compile_options(ym2610_admission_test PRIVATE /W4 /WX)
    else()
      target_compile_options(ym2610_admission_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
    glueyneo_apply_sdk_sanitizer(ym2610_admission_test)
    add_test(NAME ym2610_admission
      COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/chips/check_ym2610.py"
              test --binary $<TARGET_FILE:ym2610_admission_test>
              --report "${CMAKE_CURRENT_BINARY_DIR}/ym2610-admission/ym2610-admission.json")
    set_tests_properties(ym2610_admission PROPERTIES LABELS "ym2610-admission" TIMEOUT 180)
  endif()

  add_executable(public_guest_test
    tests/fixture/test_public_guest.c
    tests/fixture/public_guest.c
  )
  target_include_directories(public_guest_test PRIVATE tests/fixture)
  target_compile_features(public_guest_test PRIVATE c_std_17)
  set_target_properties(public_guest_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(public_guest_test PRIVATE glueyneo glueyneo_unity)
  if(MSVC)
    target_compile_options(public_guest_test PRIVATE /W4 /WX)
  else()
    target_compile_options(public_guest_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(public_guest_test)
  set(GLUEYNEO_PUBLIC_FIXTURE
      "${CMAKE_CURRENT_BINARY_DIR}/public-playable.bin")
  add_custom_command(
    OUTPUT "${GLUEYNEO_PUBLIC_FIXTURE}"
    COMMAND $<TARGET_FILE:public_guest_test> --write-fixture
            "${GLUEYNEO_PUBLIC_FIXTURE}"
    DEPENDS public_guest_test tests/fixture/public_guest.c
    VERBATIM
  )
  add_custom_target(glueyneo-public-fixture ALL
    DEPENDS "${GLUEYNEO_PUBLIC_FIXTURE}")
  add_test(NAME public_guest_contract
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}")
  add_test(NAME public_guest_trace
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" trace)
  add_test(NAME public_guest_negative_left
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" negative-left)
  add_test(NAME public_guest_negative_none
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" negative-none)
  set_tests_properties(public_guest_contract public_guest_trace
    public_guest_negative_left public_guest_negative_none PROPERTIES
    LABELS "public-fixture;native-tracer")

  add_executable(libretro_callback_test tests/libretro/callback_harness.c)
  target_include_directories(libretro_callback_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/libretro
  )
  target_compile_features(libretro_callback_test PRIVATE c_std_17)
  set_target_properties(libretro_callback_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(libretro_callback_test PRIVATE
    glueyneo_libretro Glueyneo::glueyneo ${CMAKE_DL_LIBS}
  )
  if(MSVC)
    target_compile_options(libretro_callback_test PRIVATE /W4 /WX)
  else()
    target_compile_options(libretro_callback_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(libretro_callback_test)
  add_dependencies(libretro_callback_test glueyneo-public-fixture)
  add_test(NAME libretro_callback
    COMMAND libretro_callback_test "${GLUEYNEO_PUBLIC_FIXTURE}")
  set_tests_properties(libretro_callback PROPERTIES LABELS "libretro;callback-contract")

  add_library(mvs_import_lib STATIC tools/mvs/mvs_import.c)
  target_compile_definitions(mvs_import_lib PRIVATE MVS_IMPORT_NO_MAIN)
  target_compile_features(mvs_import_lib PRIVATE c_std_17)
  set_target_properties(mvs_import_lib PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_include_directories(mvs_import_lib PRIVATE third_party/zlib)
  target_link_libraries(mvs_import_lib PRIVATE glueyneo_mvs_zlib)
  if(MSVC)
    target_compile_options(mvs_import_lib PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_import_lib PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_import_lib)

  add_executable(mvs_importer tools/mvs/mvs_import.c)
  target_compile_features(mvs_importer PRIVATE c_std_17)
  set_target_properties(mvs_importer PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_include_directories(mvs_importer PRIVATE third_party/zlib)
  target_link_libraries(mvs_importer PRIVATE glueyneo_mvs_zlib)
  if(MSVC)
    target_compile_options(mvs_importer PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_importer PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_importer)

  add_executable(mvs_test tests/mvs/test_mvs.c)
  target_include_directories(mvs_test PRIVATE
    src third_party/libretro third_party/zlib)
  target_compile_features(mvs_test PRIVATE c_std_17)
  target_compile_definitions(mvs_test PRIVATE GLUEYNEO_SDK_TEST_HOOKS)
  set_target_properties(mvs_test PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_test PRIVATE
    glueyneo_test glueyneo_unity mvs_import_lib glueyneo_libretro
    ${CMAKE_DL_LIBS})
  if(MSVC)
    target_compile_options(mvs_test PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_test)
  add_test(NAME mvs_synthetic_trace COMMAND mvs_test)
  set_tests_properties(mvs_synthetic_trace PROPERTIES
    LABELS "mvs;importer;guest;libretro" TIMEOUT 60)
  add_test(NAME mvs_media_contract COMMAND mvs_test --media-contract)
  add_test(NAME mvs_import_contract
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer> --mode positive)
  add_test(NAME mvs_import_mutation
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer> --mode mutation)
  add_test(NAME mvs_callback_contract COMMAND mvs_test --callback-contract)
  add_test(NAME mvs_boot_checkpoint COMMAND mvs_test --boot-checkpoint)
  set_tests_properties(mvs_media_contract mvs_import_contract mvs_import_mutation
    mvs_callback_contract mvs_boot_checkpoint PROPERTIES LABELS "mvs" TIMEOUT 180)

  add_executable(mvs_import_fuzz tests/mvs/fuzz_import.c)
  target_compile_features(mvs_import_fuzz PRIVATE c_std_17)
  target_link_libraries(mvs_import_fuzz PRIVATE mvs_import_lib)
  if(MSVC)
    target_compile_options(mvs_import_fuzz PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_import_fuzz PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_import_fuzz)
  add_dependencies(mvs_test mvs_import_fuzz)
  add_test(NAME mvs_import_fuzz_corpus
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer> --fuzzer $<TARGET_FILE:mvs_import_fuzz>
            --mode fuzz)
  set_tests_properties(mvs_import_fuzz_corpus PROPERTIES
    LABELS "mvs;fuzz" TIMEOUT 180)

  add_executable(mvs_qualify tools/mvs/mvs_qualify.c)
  target_include_directories(mvs_qualify PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
  target_compile_features(mvs_qualify PRIVATE c_std_17)
  set_target_properties(mvs_qualify PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_qualify PRIVATE Glueyneo::glueyneo)
  if(MSVC)
    target_compile_options(mvs_qualify PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_qualify PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_qualify)

  add_executable(sdk_diagnostic tests/sdk/test_sdk.c tests/sdk/guest_fixture.c)
  target_include_directories(sdk_diagnostic PRIVATE tests/sdk src)
  target_compile_features(sdk_diagnostic PRIVATE c_std_17)
  set_target_properties(sdk_diagnostic PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_diagnostic PRIVATE
    glueyneo_test glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_diagnostic PRIVATE Threads::Threads)
  endif()
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

  # The pinned Z80 remains a private candidate until its admission gates pass.
  add_executable(z80_admission_test
    tests/chips/test_z80.c
    src/chips/z80_candidate.c
  )
  target_include_directories(z80_admission_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/chips
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
  )
  target_compile_features(z80_admission_test PRIVATE c_std_17)
  set_target_properties(z80_admission_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(z80_admission_test PRIVATE glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(z80_admission_test PRIVATE Threads::Threads)
  endif()
  if(MSVC)
    target_compile_options(z80_admission_test PRIVATE /W4 /WX)
  else()
    target_compile_options(z80_admission_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(z80_admission_test)
  add_test(NAME z80_admission_contract COMMAND z80_admission_test)
  set_tests_properties(z80_admission_contract PROPERTIES LABELS "z80-admission")
  foreach(z80_mutation IN ITEMS cycle bus irq continuation instance)
    add_test(NAME "z80_admission_mutation_${z80_mutation}"
      COMMAND z80_admission_test "--mutation=${z80_mutation}")
    set_tests_properties("z80_admission_mutation_${z80_mutation}" PROPERTIES
      WILL_FAIL TRUE
      LABELS "z80-admission;z80-mutation"
    )
  endforeach()

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
  target_link_libraries(sdk_mutation PRIVATE glueyneo glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_mutation PRIVATE Threads::Threads)
  endif()
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
  if(WIN32)
    find_program(GLUEYNEO_SDK_DUMPBIN NAMES dumpbin REQUIRED)
  endif()
  set(SDK_HOST_CLOSURE_CONTENT [=[
set(_sdk_sources "@SDK_RUNTIME_ABSOLUTE_SOURCES@")
set(_sdk_library "$<TARGET_FILE:glueyneo>")
set(_sdk_nm "@CMAKE_NM@")
set(_sdk_windows "@WIN32@")
set(_sdk_dumpbin "@GLUEYNEO_SDK_DUMPBIN@")
set(_sdk_host_names "fopen|freopen|fread|fwrite|remove|rename|open|close|read|write|time|clock|gettimeofday|socket|connect|accept|system|fork|execve|pthread_create|pthread_mutex_lock|CreateFileA|CreateFileW|ReadFile|WriteFile|DeleteFileA|DeleteFileW|MoveFileA|MoveFileW|GetSystemTime|GetSystemTimeAsFileTime|GetSystemTimePreciseAsFileTime|GetTickCount|GetTickCount64|QueryPerformanceCounter|QueryPerformanceFrequency|timeGetTime|GetEnvironmentVariableA|GetEnvironmentVariableW|WSAStartup|closesocket|getaddrinfo|send|recv|bind|listen|CreateThread|_beginthread|_beginthreadex|CreateMutexA|CreateMutexW|WaitForSingleObject|WaitForMultipleObjects|EnterCriticalSection|AcquireSRWLockExclusive|AcquireSRWLockShared|Sleep|SleepEx|SwitchToThread")
set(_sdk_host_calls "(^|[^A-Za-z0-9_])(${_sdk_host_names})[ \t]*\\(")
foreach(_sdk_source IN LISTS _sdk_sources)
  file(READ "${_sdk_source}" _sdk_text)
  if(_sdk_text MATCHES "${_sdk_host_calls}")
    message(FATAL_ERROR "Ambient host call found in runtime source: ${_sdk_source}")
  endif()
endforeach()
if(_sdk_windows)
  # /SYMBOLS exposes each COFF object's external definitions and references in
  # the static archive. /GL objects lack this table and must fail qualification.
  # https://learn.microsoft.com/en-us/cpp/build/reference/symbols
  # Checked 2026-10-06; retain the source closure as a separate control.
  execute_process(COMMAND ${_sdk_dumpbin} /SYMBOLS "${_sdk_library}"
    RESULT_VARIABLE _sdk_dumpbin_result OUTPUT_VARIABLE _sdk_symbols
    ERROR_VARIABLE _sdk_dumpbin_error)
  if(NOT _sdk_dumpbin_result EQUAL 0)
    message(FATAL_ERROR "Could not inspect runtime COFF symbols: ${_sdk_dumpbin_error}")
  endif()
  if(NOT _sdk_symbols MATCHES "File Type:[ \t]+(LIBRARY|COFF OBJECT)" OR
     NOT _sdk_symbols MATCHES "COFF SYMBOL TABLE")
    message(FATAL_ERROR "Runtime inspector produced no recognizable COFF symbol table")
  endif()
  string(REGEX MATCHALL "COFF SYMBOL TABLE" _sdk_coff_tables "${_sdk_symbols}")
  list(LENGTH _sdk_coff_tables _sdk_coff_table_count)
  list(LENGTH _sdk_sources _sdk_source_count)
  if(NOT _sdk_coff_table_count EQUAL _sdk_source_count)
    message(FATAL_ERROR "Runtime inspector omitted one or more runtime object symbol tables")
  endif()
  string(REPLACE "\r" "" _sdk_symbols "${_sdk_symbols}")
  string(REPLACE "\n" ";" _sdk_symbol_lines "${_sdk_symbols}")
  set(_sdk_external_count 0)
  string(REGEX REPLACE "\\|_beginthread" "|beginthread"
    _sdk_windows_host_names "${_sdk_host_names}")
  foreach(_sdk_line IN LISTS _sdk_symbol_lines)
    if(_sdk_line MATCHES "[ \t](WeakExternal|External)[ \t]+\\|")
      if(NOT _sdk_line MATCHES "^[ \t]*[0-9A-Fa-f]+[ \t]+[0-9A-Fa-f]+[ \t]+(UNDEF|ABS|DEBUG|SECT[0-9A-Fa-f]+)[ \t]+[^|]*[ \t](WeakExternal|External)[ \t]+\\|[ \t]+([^ \t]+)")
        message(FATAL_ERROR "Runtime inspector produced an unrecognizable external COFF symbol row")
      endif()
      set(_sdk_symbol "${CMAKE_MATCH_3}")
      math(EXPR _sdk_external_count "${_sdk_external_count} + 1")
      # Handle imported and x86-decorated C symbols before matching exact names.
      string(REGEX REPLACE "^__imp_" "" _sdk_symbol "${_sdk_symbol}")
      string(REGEX REPLACE "^_+" "" _sdk_symbol "${_sdk_symbol}")
      string(REGEX REPLACE "@[0-9]+$" "" _sdk_symbol "${_sdk_symbol}")
      if(_sdk_symbol MATCHES "^(${_sdk_windows_host_names})$")
        message(FATAL_ERROR "Ambient host symbol found in runtime: ${_sdk_symbol}")
      endif()
      if(_sdk_symbol MATCHES "^gn_test_")
        message(FATAL_ERROR "Private test hook leaked into public runtime: ${_sdk_symbol}")
      endif()
    endif()
  endforeach()
  if(_sdk_external_count EQUAL 0)
    message(FATAL_ERROR "Runtime inspector produced no external COFF symbols")
  endif()
else()
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
