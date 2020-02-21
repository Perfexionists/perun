#ifndef PROTOTYPE_PROFILE_H
#define PROTOTYPE_PROFILE_H

// Enable g++ to call these injections
extern "C" {
    void __cyg_profile_func_enter (void *func,  void *caller);
    void __cyg_profile_func_exit (void *func, void *caller);
}

// Chrono namespaces
using namespace std::chrono;
using Time = steady_clock;

// Force timestamp record to be long long type
typedef duration<long long int, std::ratio<1ll, 1000000ll>> timestamp;

// Enables or disables the instrumentation after wrapper class construction / destruction
static bool trace_ready = false;

// Wrapper class for instrumentation. Instantiated as a static object, constructed before entering the main and
// destructed after exiting main. Last static initialization and first static destruction due to init_priority for
// safety reasons.
class Trace_context_wrapper {
    // The instrumentation data record structure
    struct Instrument_data {
        Instrument_data(char action, void *function, timestamp now, std::size_t struct_size = 0) :
                action{action}, function_address{function}, now{now}, struct_size{struct_size} {};

        char action;                    // The recorded action (into function, out of function)
        void *function_address;         // The address of recorded function
        timestamp now;                  // The timestamp of the instrumentation record
        std::size_t struct_size;        // The size of the structure the function works with
    };

    // Using vector as we need effective insertion and no additional memory usage for storage, no searching
    std::vector<Instrument_data> instr_data;

    const unsigned int max_records = 19998; // Number of records to store before printing them to the file
    std::ofstream trace_log;                // Trace output stream

public:
    Configuration config;               // Configuration object

    // Wrapper constructor, handles object initialization and configuration file parsing
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(EXIT_ERR_PROFILE_FILE_OPEN)
    // Throws:
    //  -- None
    Trace_context_wrapper();

    // Wrapper destructor.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(EXIT_ERR_PROFILE_FILE_CLOSED)
    // Throws:
    //  -- None
    ~Trace_context_wrapper();

    // Prints the current instr_data vector contents to the trace log file
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    //  -- failure: exit(EXIT_ERR_PROFILE_FILE_CLOSED)
    // Throws:
    //  -- None
    void Print_vector_to_file();

    // Prints the instrumentation record directly to the trace log file
    // ----------------------------------------------------------------
    // Arguments:
    //  -- func: Instrumented function address pointer
    //  -- io:   A character representing function entry ('i' as in) or exit ('o' as out)
    //  -- size: The size of the structure the function works with
    // Returns:
    //  -- void
    //  -- failure: exit(EXIT_ERR_PROFILE_FILE_CLOSED)
    // Throws:
    //  -- None
    void Print_record_to_file(void *func, char io, std::size_t size = 0);

    // Creates and stores the instrumentation record either to the instr_data vector or trace log file.
    // Also dumps the vector contents to the file if maximum configured records number is reached
    // Instrumentation record format: i/o func_ptr timestamp
    // ----------------------------------------------------------------
    // Arguments:
    //  -- func: Instrumented function address pointer
    //  -- io:   A character representing function entry ('i' as in) or exit ('o' as out)
    //  -- now:  The already acquired timestamp to be saved
    //  -- size: The size of the structure the function works with
    // Returns:
    //  -- void
    //  -- failure: exit(EXIT_ERR_PROFILE_FILE_CLOSED)
    // Throws:
    //  -- None
    void Create_instrumentation_record(void *func, char io);
    void Create_instrumentation_record(void *func, char io, timestamp now, std::size_t size = 0);
};

#endif //PROTOTYPE_PROFILE_H
