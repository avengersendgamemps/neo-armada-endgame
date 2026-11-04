cmake_minimum_required(VERSION 3.20)

project(NeonArmadaReferenceAgent LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Reference-agent targets will opt into these warnings when implementation begins.
add_library(neon_armada_cpp_warnings INTERFACE)
target_compile_options(neon_armada_cpp_warnings INTERFACE
    $<$<CXX_COMPILER_ID:MSVC>:/W4 /permissive->
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)
