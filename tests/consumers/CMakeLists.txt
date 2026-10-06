# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.20)
project(GlueyneoInstalledConsumer LANGUAGES C CXX)

find_package(Glueyneo 0.1.0 EXACT CONFIG REQUIRED)

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
