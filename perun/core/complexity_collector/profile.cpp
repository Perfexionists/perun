#include <chrono>
#include <vector>
#include <tuple>
#include <fstream>
#include "Configuration.h"

/*Thoughts:
 - overloaded functions filter? test first, only run-time filtering tho -- check
 - sampling on/off and rate specified for each func independently? -- check
 - force direct file output and sampling off by -D to increase speed?
 -- check if branch reduction really make such difference
 --- maybe also manually "inline" functions to make bigger difference?
*/

// Enable g++ to call these injections
extern "C" {
    void __cyg_profile_func_enter (void *func,  void *caller);
    void __cyg_profile_func_exit (void *func, void *caller);
}

// Chrono namespaces
using namespace std::chrono;
using Time = high_resolution_clock;

// Enables or disables the instrumentation after wrapper class construction / destruction
static bool trace_ready = false;

// Wrapper class for instrumentation. Instantiated as a static object, constructed before entering the main and
// destructed after exiting main. Last static initialization and first static destruction due to init_priority for
// safety reasons.
struct Trace_context_wrapper {
    Configuration config;              // Configuration object
    bool use_direct_file_output;       // Output instrumentation records directly to the file

    // Using vector as we need effective insertion and no additional memory usage for storage, no searching
    // Force timestamp record to be long long type
    std::vector<std::tuple<unsigned char, void *, duration<long long int, std::ratio<1ll, 1000000ll>>>> instr_data;

    std::ofstream trace_log;           // Trace output stream

    // Wrapper constructor, handles object initialization and configuration file parsing
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_open)
    // Throws:
    //  -- None
    Trace_context_wrapper();

    // Wrapper destructor.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_closed)
    // Throws:
    //  -- None
    ~Trace_context_wrapper();

    // Prints the current instr_data vector contents to the trace log file
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_closed)
    // Throws:
    //  -- None
    void Print_vector_to_file();

    // Prints the instrumentation record directly to the trace log file
    // ----------------------------------------------------------------
    // Arguments:
    //  -- func: Instrumented function address pointer
    //  -- io:   A character representing function entry ('i' as in) or exit ('o' as out)
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_closed)
    // Throws:
    //  -- None
    void Print_record_to_file(void *func, char io);

    // Handles vector exceptions (memory exhaustion, maximum capacity reached). Prints all the vector contents into the
    // trace log file and attempts to release memory by shrinking the vector back to the initial capacity (defined by the
    // instr_init_data_len). Also retries to store the instrumentation record with new current timestamp. In case of
    // another vector failure resorts to direct file output. Terminates if file output fails.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- func: Instrumented function address pointer
    //  -- io:   A character representing function entry ('i' as in) or exit ('o' as out)
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_closed)
    // Throws:
    //  -- None
    void Handle_vector_failure(void *func, char io);

    // Creates and stores the instrumentation record either to the instr_data vector or trace log file.
    // Instrumentation record format: i/o func_ptr timestamp
    // ----------------------------------------------------------------
    // Arguments:
    //  -- func: Instrumented function address pointer
    //  -- io:   A character representing function entry ('i' as in) or exit ('o' as out)
    // Returns:
    //  -- void
    //  -- failure: exit(exit_err_profile_file_closed)
    // Throws:
    //  -- None
    void Create_instrumentation_record(void *func, char io);
};

Trace_context_wrapper::Trace_context_wrapper() : config(), use_direct_file_output{true}
{
    // Get the configuration information
    int ret_code = config.Parse();
    if(ret_code != 0) {
        exit(ret_code);
    }

    // Setup the storage if needed
    if(!use_direct_file_output) {
        try {
            instr_data.clear();
            instr_data.reserve(config.instr_data_init_len);
        } catch (const std::bad_alloc &) {
            // Not enough memory, use file output instead
            use_direct_file_output = true;
        } catch (const std::length_error &) {
            // Unable to resize the vector to init capacity
            use_direct_file_output = true;
        }
    }

    // Open the trace log file
    trace_log.open(config.trace_file_name, std::ios::out | std::ios::trunc);
    if(!trace_log.is_open()) {
        // File opening failed, terminate
        instr_data.clear();
        config.func_config.clear();
        exit(exit_err_profile_file_open);
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
        if(!use_direct_file_output) {
            // Save the records into the trace file
            Print_vector_to_file();
        }
    } else {
        // File unexpectedly closed, terminate
        instr_data.clear();
        config.func_config.clear();
        exit(exit_err_profile_file_closed);
    }
}

void Trace_context_wrapper::Print_vector_to_file()
{
    // Print the whole vector contents to a trace log file
    if(trace_log.is_open()) {
        for(unsigned int i = 0; i < instr_data.size(); i++) {
            trace_log << std::get<0>(instr_data[i]) << " " << std::get<1>(instr_data[i]) << " "
                      << std::get<2>(instr_data[i]).count() << std::endl;
        }
    } else {
        // File unexpectedly closed
        instr_data.clear();
        config.func_config.clear();
        exit(exit_err_profile_file_closed);
    }
}

void Trace_context_wrapper::Handle_vector_failure(void *func, char io)
{
    if(trace_log.is_open()) {
        // Memory exhaustion occurred or vector bounds reached, print the contents of the vector into the trace file
        Print_vector_to_file();
        try {
            // Resize the vector to init capacity
            instr_data.clear();
            instr_data.shrink_to_fit();
            instr_data.reserve(config.instr_data_init_len);
            // Retry the instrumentation
            duration<long long int, std::ratio<1ll, 1000000ll>> timestamp = duration_cast<microseconds>(Time::now().time_since_epoch());
            instr_data.push_back(std::make_tuple(io, func, timestamp));
        } catch (const std::bad_alloc &) {
            // Not enough memory, use file output instead
            use_direct_file_output = true;
            // Retry the instrumentation
            Print_record_to_file(func, io);
        } catch (const std::length_error &) {
            // Unable to resize the vector to init capacity
            use_direct_file_output = true;
            // Retry the instrumentation
            Print_record_to_file(func, io);
        }
    } else {
        // File unexpectedly closed during data collecting, terminate
        instr_data.clear();
        config.func_config.clear();
        exit(exit_err_profile_file_closed);
    }
}

void Trace_context_wrapper::Print_record_to_file(void *func, char io)
{
    if(trace_log.is_open()) {
        // Force timestamp to be long long
        duration<long long int, std::ratio<1ll, 1000000ll>> timestamp = duration_cast<microseconds>(Time::now().time_since_epoch());
        trace_log << io << " " << func << " " << timestamp.count() << std::endl;
    } else {
        // File unexpectedly closed
        instr_data.clear();
        config.func_config.clear();
        exit(exit_err_profile_file_closed);
    }
}

void Trace_context_wrapper::Create_instrumentation_record(void *func, char io)
{
    // Vector is used for data storage
    if(!use_direct_file_output) {
        try {
            // Force timestamp to be long long
            duration<long long int, std::ratio<1ll, 1000000ll>> timestamp = duration_cast<microseconds>(Time::now().time_since_epoch());
            instr_data.push_back(std::make_tuple(io, func, timestamp));
        } catch (const std::bad_alloc &) {
            // Memory exhausted
            Handle_vector_failure(func, io);
        } catch (const std::length_error &) {
            // Vector max capacity reached
            Handle_vector_failure(func, io);
        }
    } else {
        // Direct output to the file
        Print_record_to_file(func, io);
    }
}

// Wrapper static instantiation
static Trace_context_wrapper trace __attribute__ ((init_priority (65535)));

// Functions used by injection. TODO: sampling with recursion
// ----------------------------------------------------------------
// Arguments:
//  -- None
// Returns:
//  -- void
//  -- failure: exit(exit_err_profile_file_closed)
// Throws:
//  -- None
void __cyg_profile_func_enter (void *func,  void *caller)
{
    if(trace_ready) {
        // runtime filtering and sampling
        auto result = trace.config.func_config.find(func);
        if(result != trace.config.func_config.end()) {
            if(std::get<Configuration::filter>(result->second) == Configuration::filter_on) {
                // function is filtered
                return;
            } else if(std::get<Configuration::sample>(result->second) == Configuration::sample_on) {
                // function is sampled
                std::get<Configuration::sample_curr>(result->second)++;
                if(std::get<Configuration::sample_curr>(result->second) !=
                   std::get<Configuration::sample_coeff>(result->second)) {
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
        // runtime filtering
        auto result = trace.config.func_config.find(func);
        if(result != trace.config.func_config.end()) {
            if(std::get<Configuration::filter>(result->second) == Configuration::filter_on) {
                // function is filtered
                return;
            } else if(std::get<Configuration::sample>(result->second) == Configuration::sample_on) {
                // function is sampled
                if(std::get<Configuration::sample_curr>(result->second) <
                   std::get<Configuration::sample_coeff>(result->second)) {
                    // don't record this occurrence
                    return;
                } else {
                    // record this occurrence and reset the sampling counter
                    std::get<Configuration::sample_curr>(result->second) = 0;
                }
            }
        }
        // Create the instrumentation record
        trace.Create_instrumentation_record(func, 'o');
    }
}