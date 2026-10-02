if(NOT CMAKE_C_COMPILER_ID MATCHES "^(AppleClang|Clang|GNU)$")
  message(FATAL_ERROR "The owned CPU experiment requires a Clang or GNU C compiler")
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

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME owned_cpu_negative
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/owned_cpu/negative.py
          $<TARGET_FILE:owned_cpu_diagnostic>)

foreach(target owned_cpu owned_cpu_unity owned_cpu_diagnostic owned_cpu_semantics)
  set_target_properties(${target} PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO)
endforeach()

foreach(target owned_cpu owned_cpu_diagnostic owned_cpu_semantics)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Werror)
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
