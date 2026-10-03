if(NOT CMAKE_C_COMPILER_ID MATCHES "^(AppleClang|Clang|GNU)$")
  message(FATAL_ERROR "The owned CPU experiment requires a Clang or GNU C compiler")
endif()

set(GLUEYNEO_OWNED_CPU_SANITIZER "NONE" CACHE STRING
    "Owned CPU instrumentation: NONE, ADDRESS_UNDEFINED or THREAD")
set_property(CACHE GLUEYNEO_OWNED_CPU_SANITIZER PROPERTY STRINGS
             NONE ADDRESS_UNDEFINED THREAD)
set(GLUEYNEO_OWNED_CPU_OPTIMIZATION "NONE" CACHE STRING
    "Owned CPU optimization mode: NONE or RELEASE")
set_property(CACHE GLUEYNEO_OWNED_CPU_OPTIMIZATION PROPERTY STRINGS NONE RELEASE)
if(NOT GLUEYNEO_OWNED_CPU_SANITIZER MATCHES "^(NONE|ADDRESS_UNDEFINED|THREAD)$")
  message(FATAL_ERROR "Unknown owned CPU sanitizer mode: ${GLUEYNEO_OWNED_CPU_SANITIZER}")
endif()
if(NOT GLUEYNEO_OWNED_CPU_OPTIMIZATION MATCHES "^(NONE|RELEASE)$")
  message(FATAL_ERROR "Unknown owned CPU optimization mode: ${GLUEYNEO_OWNED_CPU_OPTIMIZATION}")
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL
    "Export actual compile commands for the owned CPU source inventory" FORCE)

include(CheckCCompilerFlag)
include(CheckLinkerFlag)
set(OWNED_CPU_SANITIZER_FLAGS "")
if(GLUEYNEO_OWNED_CPU_SANITIZER STREQUAL "ADDRESS_UNDEFINED")
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=address,undefined")
  check_c_compiler_flag("-fsanitize=address,undefined" OWNED_CPU_HAS_ASAN_UBSAN_COMPILE)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  check_linker_flag(C "-fsanitize=address,undefined" OWNED_CPU_HAS_ASAN_UBSAN_LINK)
  if(NOT OWNED_CPU_HAS_ASAN_UBSAN_COMPILE OR NOT OWNED_CPU_HAS_ASAN_UBSAN_LINK)
    message(FATAL_ERROR "The selected compiler/linker cannot provide required ASan+UBSan instrumentation")
  endif()
  set(OWNED_CPU_SANITIZER_FLAGS -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all)
elseif(GLUEYNEO_OWNED_CPU_SANITIZER STREQUAL "THREAD")
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=thread")
  check_c_compiler_flag("-fsanitize=thread" OWNED_CPU_HAS_TSAN_COMPILE)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  check_linker_flag(C "-fsanitize=thread" OWNED_CPU_HAS_TSAN_LINK)
  if(NOT OWNED_CPU_HAS_TSAN_COMPILE OR NOT OWNED_CPU_HAS_TSAN_LINK)
    message(FATAL_ERROR "The selected compiler/linker cannot provide required ThreadSanitizer instrumentation")
  endif()
  set(OWNED_CPU_SANITIZER_FLAGS -fsanitize=thread -fno-omit-frame-pointer -fno-sanitize-recover=all)
endif()

set(OWNED_CPU_OPTIMIZATION_FLAGS "")
if(GLUEYNEO_OWNED_CPU_OPTIMIZATION STREQUAL "NONE")
  set(OWNED_CPU_OPTIMIZATION_FLAGS -O0)
else()
  set(OWNED_CPU_OPTIMIZATION_FLAGS -O2)
endif()

add_library(owned_cpu STATIC cpu.c)
target_include_directories(owned_cpu PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_definitions(owned_cpu PRIVATE OWNED_CPU_TEST_HOOKS=1)

add_library(owned_cpu_unity STATIC ../../third_party/unity/src/unity.c)
target_include_directories(owned_cpu_unity PUBLIC ../../third_party/unity/src)

add_executable(owned_cpu_diagnostic
  ../../tests/owned_cpu/test_diagnostic.c
  ../../tests/cpu/guest_fixture.c)
target_include_directories(owned_cpu_diagnostic PRIVATE ../../tests/cpu)
target_link_libraries(owned_cpu_diagnostic PRIVATE owned_cpu owned_cpu_unity)

add_executable(owned_cpu_semantics ../../tests/owned_cpu/test_semantics.c)
target_link_libraries(owned_cpu_semantics PRIVATE owned_cpu owned_cpu_unity)
target_compile_definitions(owned_cpu_semantics PRIVATE OWNED_CPU_TEST_HOOKS=1)

add_executable(owned_cpu_timing ../../tests/owned_cpu/test_timing.c)
target_link_libraries(owned_cpu_timing PRIVATE owned_cpu owned_cpu_unity)
target_compile_definitions(owned_cpu_timing PRIVATE OWNED_CPU_TEST_HOOKS=1)

find_package(Threads REQUIRED)
add_executable(owned_cpu_isolation
  ../../tests/owned_cpu/test_isolation.c
  ../../tests/cpu/guest_fixture.c)
target_include_directories(owned_cpu_isolation PRIVATE
  ${PROJECT_SOURCE_DIR}/tests/owned_cpu ${PROJECT_SOURCE_DIR}/tests/cpu)
target_link_libraries(owned_cpu_isolation PRIVATE owned_cpu owned_cpu_unity Threads::Threads)

add_executable(owned_cpu_cold
  ../../tests/owned_cpu/test_cold.c
  ../../tests/cpu/guest_fixture.c)
target_include_directories(owned_cpu_cold PRIVATE
  ${PROJECT_SOURCE_DIR}/tests/owned_cpu ${PROJECT_SOURCE_DIR}/tests/cpu)
target_link_libraries(owned_cpu_cold PRIVATE owned_cpu owned_cpu_unity Threads::Threads)

add_executable(owned_cpu_faults
  ../../tests/owned_cpu/test_faults.c
  ../../tests/cpu/guest_fixture.c)
target_include_directories(owned_cpu_faults PRIVATE
  ${PROJECT_SOURCE_DIR}/tests/owned_cpu ${PROJECT_SOURCE_DIR}/tests/cpu)
target_link_libraries(owned_cpu_faults PRIVATE owned_cpu owned_cpu_unity)
target_compile_definitions(owned_cpu_faults PRIVATE OWNED_CPU_TEST_HOOKS=1)

add_executable(owned_cpu_state ../../tests/owned_cpu/test_state.c)
target_link_libraries(owned_cpu_state PRIVATE owned_cpu owned_cpu_unity)
target_compile_definitions(owned_cpu_state PRIVATE OWNED_CPU_TEST_HOOKS=1)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME owned_cpu_negative
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/negative.py
          $<TARGET_FILE:owned_cpu_diagnostic> --state $<TARGET_FILE:owned_cpu_state>)
add_test(NAME owned_cpu_isolation_negative
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/negative.py
          --isolation $<TARGET_FILE:owned_cpu_isolation>)

set(OWNED_CPU_TARGETS owned_cpu owned_cpu_unity owned_cpu_diagnostic
    owned_cpu_semantics owned_cpu_timing owned_cpu_isolation owned_cpu_cold
    owned_cpu_faults owned_cpu_state)
foreach(target IN LISTS OWNED_CPU_TARGETS)
  set_target_properties(${target} PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Werror
    ${OWNED_CPU_OPTIMIZATION_FLAGS} ${OWNED_CPU_SANITIZER_FLAGS})
endforeach()

foreach(target owned_cpu_diagnostic owned_cpu_semantics owned_cpu_timing
               owned_cpu_isolation owned_cpu_cold owned_cpu_faults owned_cpu_state)
  target_link_options(${target} PRIVATE ${OWNED_CPU_SANITIZER_FLAGS})
endforeach()

add_test(NAME owned_cpu_diagnostic COMMAND owned_cpu_diagnostic)
set_tests_properties(owned_cpu_diagnostic PROPERTIES
  LABELS "owned-cpu;owned-diagnostic"
  TIMEOUT 30)
add_test(NAME owned_cpu_semantics COMMAND owned_cpu_semantics)
set_tests_properties(owned_cpu_semantics PROPERTIES
  LABELS "owned-cpu;owned-diagnostic"
  TIMEOUT 30)
set_tests_properties(owned_cpu_negative PROPERTIES
  LABELS "owned-cpu;owned-diagnostic-control"
  TIMEOUT 30)
add_test(NAME owned_cpu_timing COMMAND owned_cpu_timing)
set_tests_properties(owned_cpu_timing PROPERTIES
  LABELS "owned-cpu;owned-timing"
  TIMEOUT 30)
add_test(NAME owned_cpu_timing_negative
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/negative_timing.py
          $<TARGET_FILE:owned_cpu_timing>)
set_tests_properties(owned_cpu_timing_negative PROPERTIES
  LABELS "owned-cpu;owned-timing-control"
  TIMEOUT 30)
add_test(NAME owned_cpu_unsupported_negative
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/negative_timing.py
          --unsupported $<TARGET_FILE:owned_cpu_timing>)
set_tests_properties(owned_cpu_unsupported_negative PROPERTIES
  LABELS "owned-cpu;owned-timing-control"
  TIMEOUT 30)
add_test(NAME owned_cpu_isolation COMMAND owned_cpu_isolation)
set_tests_properties(owned_cpu_isolation PROPERTIES
  LABELS "owned-cpu;owned-safety"
  TIMEOUT 30)
set_tests_properties(owned_cpu_isolation_negative PROPERTIES
  LABELS "owned-cpu;owned-safety;owned-safety-control"
  TIMEOUT 30)
add_test(NAME owned_cpu_cold
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/cold.py
          $<TARGET_FILE:owned_cpu_cold>)
set_tests_properties(owned_cpu_cold PROPERTIES
  LABELS "owned-cpu;owned-safety"
  TIMEOUT 30)
add_test(NAME owned_cpu_faults COMMAND owned_cpu_faults)
set_tests_properties(owned_cpu_faults PROPERTIES
  LABELS "owned-cpu;owned-safety"
  TIMEOUT 30)
add_test(NAME owned_cpu_state COMMAND owned_cpu_state)
set_tests_properties(owned_cpu_state PROPERTIES
  LABELS "owned-cpu;owned-state"
  TIMEOUT 30)
add_test(NAME owned_cpu_inventory
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/test_inventory.py)
set_tests_properties(owned_cpu_inventory PROPERTIES
  LABELS "owned-cpu;owned-safety"
  TIMEOUT 30)
add_test(NAME owned_cpu_inventory_check
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/owned_cpu/inventory.py
          check --build-dir ${CMAKE_BINARY_DIR})
set_tests_properties(owned_cpu_inventory_check PROPERTIES
  LABELS "owned-cpu;owned-safety"
  TIMEOUT 30)
