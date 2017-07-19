#ifndef CPP_BASIC_CONFIGURATION_H
#define CPP_BASIC_CONFIGURATION_H

#include <unordered_map>
#include <string>
#include <fstream>
#include <exception>

// List of possible error exit codes
enum Exit_error_codes {
    EXIT_ERR_PROFILE_FILE_OPEN        = 1,  // profile output file cannot be opened
    EXIT_ERR_PROFILE_FILE_CLOSED      = 2,  // profile output file closed unexpectedly
    EXIT_ERR_CONFIG_FILE_OPEN         = 11, // configuration file does not exist
    EXIT_ERR_CONFIG_FILE_SYNTAX       = 12, // configuration file incorrect syntax
};


// A class for parsing and storage of complexity collector's runtime configuration information.
// The configuration format is specified in the 'circ.rst' file.
// Notably output file name, runtime filtering and sampling can be configured.
class Configuration {
public:
    static const int sample_init = 0;       // Default sampling configuration value

    // Function configuration storage format
    struct Config_details {
        // Config details constructor with default init list
        Config_details(bool filter = false, bool sample = false,
                       int current_sample = sample_init, int  sample_ratio = sample_init) :
                is_filtered{filter}, is_sampled{sample}, sample_current{current_sample}, sample_ratio{sample_ratio} {}

        bool is_filtered;                   // function filter on/off
        bool is_sampled;                    // function sample on/off
        int sample_current;                 // sampling counter
        int sample_ratio;                   // the sampling ratio (i.e. the sampling counter max value)
    };

    // Unordered map for function configuration storage, function pointer used as a key.
    std::unordered_map<void *, Config_details> func_config;

    std::string trace_file_name;                                // Trace log file name
    unsigned long instr_data_init_len;                          // Initial storage capacity for instrumentation records
    bool use_direct_file_output;                                // Direct output or saving data

    const unsigned long default_instr_data_init_len = 20000;    // Default instrumentation record storage capacity

    // Custom exception class for reporting a missing configuration file
    class Conf_file_missing_exception : public std::exception {};
    // Custom exception class for reporting a syntax error in the configuration file
    class Conf_file_syntax_exception : public std::exception {};

    // Configuration constructor, handles object initialization
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- None
    Configuration();

    // Configuration file parsing method. Parses and stores the
    // configuration into the class data structures func_config,
    // instr_data_init_len and trace_file_name.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- 0:    configuration data parsed ok
    //  -- else: error code as specified in the exit_error_codes
    // Throws:
    //  -- None
    int Parse();

private:
    // Configuration sections parsing status (false - not yet parsed, true - already parsed)
    // internal_data_filename ; internal_storage_size ; internal_direct_output ; runtime_filter ; sampling
    typedef std::array<bool, 5> parsed_info;
    // Convenience sections access constants
    const unsigned int section_name      = 0;                   // internal_data_filename
    const unsigned int section_storage   = 1;                   // internal_storage_size
    const unsigned int section_output    = 2;                   // internal_direct_output
    const unsigned int section_filter    = 3;                   // runtime-filter
    const unsigned int section_sampling  = 4;                   // sampling

    std::string file_contents;                                  // Buffered configuration file content
    parsed_info configuration_parsed;                           // Parsing status

    const std::string config_file_name = "circ.conf";          // Default configuration file name

    // Lexical analysis token types, more details in 'circ.conf'
    enum class Token_t {
        Default,            // Initial token type
        Magic,              // Magic code - CIRC
        Text_value,         // Textual value
        Number_value,       // Decimal number value
        Bool_value,         // Boolean value
        Op_colon,           // Operator :
        Op_equals,          // Operator =
        Br_curly_begin,     // Brace type {
        Br_curly_end,       // Brace type }
        Br_square_begin,    // Brace type [
        Br_square_end,      // Brace type ]
        Comma,              // Separator ,
        File_end            // Token indicating the end of configuration file
    };

    // Lexical analysis FSM states
    enum class FSM_token_states {
        Init,               // Initial automaton state
        Text,               // Textual value state
        Number,             // Number value state
        Magic,              // Magic code state
        Bool                // Boolean value state
    };

    // Method loads the configuration file contents into the file_contents
    // for faster text traverse and access.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- None
    // Throws:
    //  -- Conf_file_missing_exception: in case of missing configuration file
    void Load_file();

    // Method provides next lexical token from the configuration content.
    // The token is defined by its type and value.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- type:  contains token type
    //  -- value: contains token value
    // Returns:
    //  -- true:  next token is acquired
    //  -- false: end of input, token type File_end
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    bool Next_token(Token_t &type, std::string &value);

    // Method acquires next token, performs type checking on the new
    // token and provides its value
    // ----------------------------------------------------------------
    // Arguments:
    //  -- expected_tok_type:  contains the expected type of the new token
    //  -- tok_val:            contains the next token value
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax or type mismatch
    void Test_next_token_type(const Token_t &expected_tok_type, std::string &tok_val);

    // Method performs type checking on the current token
    // ----------------------------------------------------------------
    // Arguments:
    //  -- expected_tok_type:  contains the expected type of the current token
    //  -- tok_type:           contains the actual type of the current token
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of type mismatch
    void Test_token_type(const Token_t &expected_tok_type, const Token_t &tok_type);

    // Method performs value checking on the current token
    // ----------------------------------------------------------------
    // Arguments:
    //  -- expected_tok_val:  contains the expected value of the current token
    //  -- tok_val:           contains the actual value of the current token
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of value mismatch
    void Test_token_val(const std::string &expected_tok_val, const std::string &tok_val);

    // Method parses the initial configuration sequence consisting of
    // CIRC = { tokens.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    void Parse_init();

    // Method parses the internal_data_filename configuration sequence consisting of
    // 'internal_data_filename' : 'logfile-name' tokens.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    void Parse_file_name();

    // Method parses the internal_storage_size configuration sequence
    // consisting of 'internal_storage_size' : number_value tokens and
    // converts the size to a numeric type.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    //  -- invalid_argument:           if the conversion to numeric type cannot be performed
    //  -- out_of_range:               value is out of the representable range of numeric type
    void Parse_storage_size();

    // Method parses the internal_direct_output configuration sequence
    // consisting of 'internal_direct_output' : bool_value tokens.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    //  -- invalid_argument:           if the conversion to numeric type cannot be performed
    //  -- out_of_range:               value is out of the representable range of numeric type
    void Parse_direct_output();

    // Method parses the runtime-filter configuration consisting of
    // filtered addresses.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    void Parse_filter();

    // Method parses the sampling configuration consisting of addresses
    // that will be sampled and the sampling coefficient converted to
    // a numeric type.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    //  -- invalid_argument:           if the conversion to numeric type cannot be performed
    //  -- out_of_range:               value is out of the representable range of numeric type
    void Parse_sample();

    // Method performs test of duplicit configuration sections.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- index: section that will be tested
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of section duplicity
    //  -- out_of_range:               section index is out of range
    void Already_parsed_check(unsigned int index);

    // Method performs conversion from address token value to the actual
    // address pointer.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- address:  address token
    //  -- addr:     actual memory address pointer
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of failed conversion
    void Address_token_to_pointer(const std::string &address, void **addr);
};


#endif //CPP_BASIC_CONFIGURATION_H
