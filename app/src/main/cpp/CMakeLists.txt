cmake_minimum_required(VERSION 3.22.1)
project(ngrhost C)

add_library(ngrhost SHARED ngrhost.c ngr_profile.c)
find_library(log-lib log)
find_library(android-lib android)
target_compile_features(ngrhost PRIVATE c_std_11)
target_compile_options(ngrhost PRIVATE -Wall -Wextra -Werror=return-type -fvisibility=hidden)
target_link_libraries(ngrhost PRIVATE ${log-lib} ${android-lib} dl)
