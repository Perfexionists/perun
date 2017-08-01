#include <chrono>
#include <vector>
#include <tuple>
#include <fstream>
#include "configuration.h"
#include "profile.h"
#include "profile_api.h"

/*Thoughts:
 - overloaded functions filter? test first, only run-time filtering tho -- check
 - sampling on/off and rate specified for each func independently? -- check
 - force direct file output and sampling off by -D to increase speed?
 -- check if branch reduction really make such difference
 --- maybe also manually "inline" functions to make bigger difference?
*/


Trace_context_wrapper::Trace_context_wrapper() : config()
{
    // Get the configuration information
    int ret_code = config.Parse();
    if(ret_code != 0) {
        exit(ret_code);
    }

    // Setup the storage if needed
    if(config.use_direct_file_output == false) {
        try {
            instr_data.clear();
            instr_data.reserve(config.instr_data_init_len);
        } catch (const std::length_error &) {
            // Unable to resize the vector to init capacity
            // The user might have requested too much of a space, try with the default settings
            try {
                instr_data.reserve(config.default_instr_data_init_len);
            } catch(const std::length_error &) {
                // The ultimate fail, resort to the direct file output
                config.use_direct_file_output = true;
            }
        }
    }

    // Open the trace log file
    trace_log.open(config.trace_file_name, std::ios::out | std::ios::trunc);
    if(trace_log.is_open() == false) {
        // File opening failed, terminate
        instr_data.clear();
        config.func_config.clear();
        exit(EXIT_ERR_PROFILE_FILE_OPEN);
    }

    // Enables the instrumentation
    trace_ready = true;
}

Trace_context_wrapper::~Trace_context_wrapper()
{
    // Disables the instrumentation
    trace_ready = false;

    if(trace_log.is_open()) {
        // Records are stored in the vector
        if(config.use_direct_file_output == false) {
            // Save the records into the trace file
            Print_vector_to_file();
        }
    } else {
        // File unexpectedly closed, terminate
        instr_data.clear();
        config.func_config.clear();
        exit(EXIT_ERR_PROFILE_FILE_CLOSED);
    }
}

void Trace_context_wrapper::Print_vector_to_file()
{
    // Print the whole vector contents to a trace log file
    if(trace_log.is_open()) {
        for(unsigned int i = 0; i < instr_data.size(); i++) {
            trace_log << instr_data[i].action << " " << instr_data[i].function_address << " "
                      << instr_data[i].now.count() << " " << instr_data[i].struct_size << std::endl;
        }
        instr_data.clear();
    } else {
        // File unexpectedly closed
        instr_data.clear();
        config.func_config.clear();
        exit(EXIT_ERR_PROFILE_FILE_CLOSED);
    }
}

void Trace_context_wrapper::Print_record_to_file(void *func, char io, std::size_t size)
{
    if(trace_log.is_open()) {
        timestamp now = duration_cast<microseconds>(Time::now().time_since_epoch());
        trace_log << io << " " << func << " " << now.count() << " " << size << std::endl;
    } else {
        // File unexpectedly closed
        instr_data.clear();
        config.func_config.clear();
        exit(EXIT_ERR_PROFILE_FILE_CLOSED);
    }
}

void Trace_context_wrapper::Create_instrumentation_record(void *func, char io)
{
    // Clear the vector if it's size already reached configured maximum
    if(instr_data.size() >= max_records) {
        Print_vector_to_file();
    }

    // Vector is used for data storage
    if(config.use_direct_file_output == false) {
        timestamp now = duration_cast<microseconds>(Time::now().time_since_epoch());
        instr_data.push_back(Instrument_data(io, func, now));
    } else {
        // Direct output to the file
        Print_record_to_file(func, io);
    }
}

void Trace_context_wrapper::Create_instrumentation_record(void *func, char io, timestamp now, std::size_t size)
{
    // Vector is used for data storage
    if(config.use_direct_file_output == false) {
        instr_data.push_back(Instrument_data(io, func, now, size));
    } else {
        // Direct output to the file
        Print_record_to_file(func, io, size);
    }

    // Clear the vector if it's size already reached configured maximum
    if(instr_data.size() >= max_records) {
        Print_vector_to_file();
    }
}

// Wrapper static instantiation
static Trace_context_wrapper trace __attribute__ ((init_priority (65535)));

// Functions used by injection.
// ----------------------------------------------------------------
// Arguments:
//  -- None
// Returns:
//  -- void
//  -- failure: exit(EXIT_ERR_PROFILE_FILE_CLOSED)
// Throws:
//  -- None
void __cyg_profile_func_enter (void *func,  void *caller)
{
    if(trace_ready) {
        // runtime filtering and sampling
        auto result = trace.config.func_config.find(func);
        if(result != trace.config.func_config.end()) {
            if(result->second.is_filtered) {
                // function is filtered
                return;
            } else if(result->second.is_sampled) {
                // function is sampled
                result->second.sample_current++;
                if(result->second.sample_current != result->second.sample_ratio) {
                    // don't record this occurrence
                    return;
                }
            }
        }

        // Create the instrumentation record
        trace.Create_instrumentation_record(func, 'i');
    }
}
 
void __cyg_profile_func_exit (void *func, void *caller)
{
    if(trace_ready) {
        timestamp now = duration_cast<microseconds>(Time::now().time_since_epoch());
        // runtime filtering
        auto result = trace.config.func_config.find(func);
        if(result != trace.config.func_config.end()) {
            if(result->second.is_filtered) {
                // function is filtered
                return;
            } else if(result->second.is_sampled) {
                // function is sampled
                if(result->second.sample_current < result->second.sample_ratio) {
                    // don't record this occurrence
                    // remove the size record
                    _profapi_remove_size_record(__builtin_frame_address(1));
                    return;
                } else {
                    // record this occurrence and reset the sampling counter
                    result->second.sample_current = Configuration::sample_init;
                }
            }
        }

        // Create the instrumentation record
        size_t struct_size = _profapi_get_size_record(__builtin_frame_address(1));
        trace.Create_instrumentation_record(func, 'o', now, struct_size);
    }
}
