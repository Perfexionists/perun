#ifndef CPP_BASIC_CONFIGURATION_H
#define CPP_BASIC_CONFIGURATION_H

#include <unordered_map>
#include <string>
#include <fstream>
#include <exception>

// List of possible error exit codes
enum exit_error_codes {
    exit_err_profile_file_open        = 1,  // profile output file cannot be opened
    exit_err_profile_file_closed      = 2,  // profile output file closed unexpectedly
    exit_err_config_file_open         = 11, // configuration file does not exist
    exit_err_config_file_syntax       = 12, // configuration file incorrect syntax
    exit_err_config_alloc_failed      = 13, // unable to allocate needed memory for configuration data
};


// A class for parsing and storage of complexity collector's runtime configuration information.
// The configuration format is specified in the 'ccicc.rst' file.
// Notably output file name, runtime filtering and sampling can be configured.
class Configuration {
public:
    // Function configuration storage format
    // filter on/off ; sample on/off ; current sample ; sampling coefficient
    typedef std::tuple<bool, bool, int, int> config_details;

    // Unordered map for function configuration storage, function pointer used as a key.
    std::unordered_map<void *, config_details> func_config;
    unsigned long instr_data_init_len;      // Initial storage capacity for instrumentation records
    std::string trace_file_name;            // Trace log file name

    // Set of named constants for convenient config_details access
    static const int filter         = 0;    // filtering info index
    static const int sample         = 1;    // sampling info index
    static const int sample_curr    = 2;    // current function sample
    static const int sample_coeff   = 3;    // sampling coefficient
    static const bool filter_on;            // function is filtered
    static const bool filter_off;           // function is not filtered
    static const bool sample_on;            // function is sampled
    static const bool sample_off;           // function is not sampled

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
    // file-name ; storage-init-size ; runtime-filter ; sampling
    typedef std::array<bool, 4> parsed_info;
    // Convenience sections access constants
    const unsigned int section_name      = 0;    // file-name
    const unsigned int section_storage   = 1;    // storage-init-size
    const unsigned int section_filter    = 2;    // runtime-filter
    const unsigned int section_sampling  = 3;    // sampling

    std::string file_contents;          // Buffered configuration file content
    parsed_info configuration_parsed;   // Parsing status

    const unsigned long default_instr_data_init_len = 20000;    // Default instrumentation record storage capacity
    const std::string config_file_name = "ccicc.conf";          // Default configuration file name
    const int sample_init = 0;                                  // Default sampling configuration value

    // Lexical analysis token types, more details in 'ccicc.conf'
    enum class Token_t {
        Default,            // Initial token type
        Magic,              // Magic code - CCICC
        Text_value,         // Textual value
        Number_value,       // Decimal number value
        Address_value,      // Hexadecimal address value
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
        Address,            // Address value state
        Number,             // Number value state
        Magic               // Magic code state
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
    // CCICC = { tokens.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    void Parse_init();

    // Method parses the file-name configuration sequence consisting of
    // 'file-name' : 'logfile-name' tokens.
    // ----------------------------------------------------------------
    // Arguments:
    //  -- None
    // Returns:
    //  -- void
    // Throws:
    //  -- Conf_file_syntax_exception: in case of invalid configuration syntax
    void Parse_file_name();

    // Method parses the storage-init-size configuration sequence
    // consisting of 'storage-init-size' : number_value tokens and
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
