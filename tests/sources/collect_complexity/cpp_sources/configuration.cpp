#include <cctype>
#include <sstream>
#include "configuration.h"

Configuration::Configuration() : trace_file_name("trace.log"), instr_data_init_len{default_instr_data_init_len},
                                 use_direct_file_output(false)
{
    configuration_parsed.fill(false);
}

int Configuration::Parse() {
    // Token type and value
    Token_t tok_type;
    std::string tok_val;

    try {
        // Load the configuration file
        Load_file();
        // Parsing the initial sequence
        Parse_init();
        // Parsing the file contents
        // Each cycle parses one section, there are four sections in total and none can be repeated
        // In case of section repetition, invalid section or invalid token, an exception is thrown
        // Basically if anything goes wrong then exception is thrown and loop breaks
        while (1) {
            Test_next_token_type(Token_t::Text_value, tok_val);
            if (tok_val == "\"internal_data_filename\"") {
                // File name section
                Already_parsed_check(section_name);
                Parse_file_name();
            } else if (tok_val == "\"internal_storage_size\"") {
                // Storage size section
                Already_parsed_check(section_storage);
                Parse_storage_size();
            } else if (tok_val == "\"internal_direct_output\"") {
                // Direct output section
                Already_parsed_check(section_output);
                Parse_direct_output();
            } else if (tok_val == "\"runtime_filter\"") {
                // Filter section
                Already_parsed_check(section_filter);
                Parse_filter();
            } else if (tok_val == "\"sampling\"") {
                // Sampling section
                Already_parsed_check(section_sampling);
                Parse_sample();
            } else {
                // Unknown section
                throw Conf_file_syntax_exception();
            }
            // Check for a next section
            Next_token(tok_type, tok_val);
            if (tok_type == Token_t::Br_curly_end) {
                break;
            }
            Test_token_type(Token_t::Comma, tok_type);
        }
        // Configuration end
        Test_next_token_type(Token_t::File_end, tok_val);
        return 0;
    } catch(Conf_file_missing_exception &) {
        // Config file missing
        func_config.clear();
        return EXIT_ERR_CONFIG_FILE_OPEN;
    } catch(Conf_file_syntax_exception &) {
        // Other failures
        func_config.clear();
        return EXIT_ERR_CONFIG_FILE_SYNTAX;
    }
}

void Configuration::Load_file() {
    // Open the config file
    std::ifstream config_file(config_file_name, std::ios::in);
    if(config_file.is_open() == false) {
        // Configuration file is missing
        throw Conf_file_missing_exception();
    }
    // Read the whole config file
    std::ostringstream file_buff;
    file_buff << config_file.rdbuf();
    file_contents = file_buff.str();
}

bool Configuration::Next_token(Token_t &type, std::string &value)
{
    // Init the FSM
    static size_t position = 0;
    value.clear();
    type = Token_t::Default;
    FSM_token_states FSM_token = FSM_token_states::Init;

    while(position < file_contents.length()) {
        char c = file_contents[position++];
        if(FSM_token == FSM_token_states::Init) {
            // Get rid of a whitespace
            if(isspace(c)) {
                continue;
            }

            // Check for short tokens first
            if(c == '=') {
                type = Token_t::Op_equals;
            } else if(c == ':') {
                type = Token_t::Op_colon;
            } else if(c == '[') {
                type = Token_t::Br_square_begin;
            } else if(c == ']') {
                type = Token_t::Br_square_end;
            } else if(c == '{') {
                type = Token_t::Br_curly_begin;
            } else if(c == '}') {
                type = Token_t::Br_curly_end;
            } else if(c == ',') {
                type = Token_t::Comma;
            }
            if(type != Token_t::Default) {
                // Token was already recognized
                value += c;
                return true;
            }

            // Check for longer tokens
            if(c == '"') {
                FSM_token = FSM_token_states::Text;
                type = Token_t::Text_value;
            } else if(c == 'C') {
                FSM_token = FSM_token_states::Magic;
                type = Token_t::Magic;
            } else if(isdigit(c)) {
                FSM_token = FSM_token_states::Number;
                type = Token_t::Number_value;
            } else if(c == 'f' || c == 't') {
                FSM_token = FSM_token_states::Bool;
                type = Token_t::Bool_value;
            } else {
                // Invalid character, error
                throw Conf_file_syntax_exception();
            }
            value += c;
        } else if(FSM_token == FSM_token_states::Text) {
            // Text token
            value += c;
            if(c == '"') {
                return true;
            }
        } else if(FSM_token == FSM_token_states::Number) {
            // Number token
            if(isdigit(c)) {
                value += c;
            } else {
                position--;
                return true;
            }
        } else if(FSM_token == FSM_token_states::Magic) {
            // Magic code token
            if(c == 'C' || c == 'I' || c == 'R') {
                value += c;
            } else if(value == "CIRC") {
                position--;
                return true;
            } else {
                throw Conf_file_syntax_exception();
            }
        } else {
            // Bool token
            if(c == 'a' || c == 'l' || c == 's' || c == 'e' || c == 'r' || c == 'u') {
                value += c;
            } else if(value == "false" || value == "true") {
                position--;
                return true;
            } else {
                throw Conf_file_syntax_exception();
            }
        }
    }

    // Out of tokens
    if(FSM_token == FSM_token_states::Init) {
        type = Token_t::File_end;
        return false;
    } else {
        // Unexpected token interrupt
        throw Conf_file_syntax_exception();
    }

}

void Configuration::Test_next_token_type(const Token_t &expected_tok_type, std::string &tok_val) {
    Token_t tok_type;

    Next_token(tok_type, tok_val);
    if(tok_type != expected_tok_type) {
        // Token types don't match
        throw Conf_file_syntax_exception();
    }
}

void Configuration::Test_token_type(const Token_t &expected_tok_type, const Token_t &tok_type) {
    if(tok_type != expected_tok_type) {
        // Token types don't match
        throw Conf_file_syntax_exception();
    }
}

void Configuration::Test_token_val(const std::string &expected_tok_val, const std::string &tok_val) {
    if(tok_val != expected_tok_val) {
        // Token values don't match
        throw Conf_file_syntax_exception();
    }
}

void Configuration::Parse_init() {
    std::string tok_val;

    Test_next_token_type(Token_t::Magic, tok_val);
    Test_next_token_type(Token_t::Op_equals, tok_val);
    Test_next_token_type(Token_t::Br_curly_begin, tok_val);
}

void Configuration::Parse_file_name() {
    std::string tok_val;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Text_value, tok_val);
    // Remove the apostrophes
    trace_file_name = tok_val.substr(1, tok_val.length() - 2);
}

void Configuration::Parse_storage_size() {
    std::string tok_val;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Number_value, tok_val);
    // Convert to a unsigned long
    instr_data_init_len = std::stoul(tok_val);
}

void Configuration::Parse_direct_output() {
    std::string tok_val;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Bool_value, tok_val);
    //Convert to a bool
    if(tok_val == "false") {
        use_direct_file_output = false;
    } else {
        use_direct_file_output = true;
    }
}

void Configuration::Parse_filter() {
    Token_t tok_type;
    std::string tok_val;
    void *func_p;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Br_square_begin, tok_val);

    // Traverse the collection
    // Comma token means the collection traversal continues, ending curly brace means end to the collection
    // Exception is thrown if unexpected token is received
    while(1) {
        // address, address, ...
        Test_next_token_type(Token_t::Number_value, tok_val);
        // Convert to the pointer
        Address_token_to_pointer(tok_val, &func_p);

        // The function is to be filtered, overwrite previous configuration if any
        func_config[func_p] = Config_details(true);

        // Test for the collection end
        Next_token(tok_type, tok_val);
        if(tok_type == Token_t::Br_square_end) {
            break;
        }
        Test_token_type(Token_t::Comma, tok_type);
    }
}

void Configuration::Parse_sample() {
    Token_t tok_type;
    std::string tok_val;
    void *func_p;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Br_square_begin, tok_val);
    // Traverse the collection
    // Comma token means the collection traversal continues, ending curly brace means end to the collection
    // Exception is thrown if unexpected token is received
    while(1) {
        // { "func" : address, "sample": number },
        Test_next_token_type(Token_t::Br_curly_begin, tok_val);
        Test_next_token_type(Token_t::Text_value, tok_val);
        Test_token_val("\"func\"", tok_val);
        Test_next_token_type(Token_t::Op_colon, tok_val);
        Test_next_token_type(Token_t::Number_value, tok_val);
        // Convert the address to a pointer
        Address_token_to_pointer(tok_val, &func_p);
        Test_next_token_type(Token_t::Comma, tok_val);
        Test_next_token_type(Token_t::Text_value, tok_val);
        Test_token_val("\"sample\"", tok_val);
        Test_next_token_type(Token_t::Op_colon, tok_val);
        Test_next_token_type(Token_t::Number_value, tok_val);
        // Convert the sample to a integer
        int sample_val = std::stoi(tok_val);

        // Search for the function configuration record
        auto func_record = func_config.find(func_p);
        if(func_record == func_config.end()) {
            // Function does not have a configuration record yet, create one
            // If the sampling is lower than/or one, do not create sampling record as it would only slow down instrumentation
            if(sample_val > 1) {
                func_config.insert({func_p, Config_details(false, true, sample_val - 1, sample_val)});
            }
        }
        // There is no need to update the record if it already exists
        // Either the function is supposed to be filtered or multiple definition for sampling - we take the first one

        Test_next_token_type(Token_t::Br_curly_end, tok_val);

        // Test for the collection end
        Next_token(tok_type, tok_val);
        if(tok_type == Token_t::Br_square_end) {
            break;
        }
        Test_token_type(Token_t::Comma, tok_type);
    }
}

void Configuration::Already_parsed_check(const unsigned int index) {
    if(configuration_parsed.at(index) == true) {
        // section duplicity
        throw Conf_file_syntax_exception();
    } else {
        // set the section as already parsed
        configuration_parsed.at(index) = true;
    }
}

void Configuration::Address_token_to_pointer(const std::string &address, void **addr) {
    // Convert the decimal address string representation to hex address string format
    unsigned long long address_dec = std::stoull(address);
    std::stringstream to_addr;
    to_addr << "0x" << std::hex << address_dec;
    std::string address_hex(to_addr.str());

    if(sscanf(address_hex.c_str(), "0x%p", addr) != 1) {
        // Conversion to a pointer failed
        throw Conf_file_syntax_exception();
    }
}
