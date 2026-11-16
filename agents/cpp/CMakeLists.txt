cmake_minimum_required(VERSION 3.20)

project(NeonArmadaCppAgents LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# All executables land in <build>/bin, also with multi-config generators
# (Visual Studio, Xcode), so the agent path is the same on every platform:
#   build/cpp/bin/neon_starter_agent[.exe]
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
foreach(config Debug Release RelWithDebInfo MinSizeRel)
    string(TOUPPER "${config}" config_upper)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${config_upper} "${CMAKE_BINARY_DIR}/bin")
endforeach()

add_library(neon_armada_cpp_warnings INTERFACE)
target_compile_options(neon_armada_cpp_warnings INTERFACE
    $<$<CXX_COMPILER_ID:MSVC>:/W4 /permissive->
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)

# Header-only starter kit.
add_library(neon_agent_kit INTERFACE)
target_include_directories(neon_agent_kit INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/include")

# Functional starter agent built on the kit.
add_executable(neon_starter_agent src/starter_agent.cpp)
target_link_libraries(neon_starter_agent PRIVATE neon_agent_kit neon_armada_cpp_warnings)
