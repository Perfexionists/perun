#include <cctype>
#include <sstream>
#include "Configuration.h"

// static class-scoped constants declaration
const bool Configuration::filter_on = true;
const bool Configuration::filter_off = false;
const bool Configuration::sample_on = true;
const bool Configuration::sample_off = false;
//const bool Configuration::sample_init;

Configuration::Configuration() : instr_data_init_len{default_instr_data_init_len}, trace_file_name("trace.log")
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
        while (1) {
            Test_next_token_type(Token_t::Text_value, tok_val);
            if (tok_val == "'file-name'") {
                // File name section
                Already_parsed_check(section_name);
                Parse_file_name();
            } else if (tok_val == "'storage-init-size'") {
                // Storage size section
                Already_parsed_check(section_storage);
                Parse_storage_size();
            } else if (tok_val == "'runtime-filter'") {
                // Filter section
                Already_parsed_check(section_filter);
                Parse_filter();
            } else if (tok_val == "'sampling'") {
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
        return exit_err_config_file_open;
    } catch(std::bad_alloc &) {
        // Out of memory
        return exit_err_config_alloc_failed;
    } catch(std::exception &) {
        // Other failures
        func_config.clear();
        return exit_err_config_file_syntax;
    }
}

void Configuration::Load_file() {
    // Open the config file
    std::ifstream config_file(config_file_name, std::ios::in);
    if(!config_file) {
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
    char c;

    while(position < file_contents.length()) {
        c = file_contents[position++];
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
            if(c == '\'') {
                FSM_token = FSM_token_states::Text;
                type = Token_t::Text_value;
            } else if(c == 'C') {
                FSM_token = FSM_token_states::Magic;
                type = Token_t::Magic;
            } else if(c == '0') {
                FSM_token = FSM_token_states::Address;
                type = Token_t::Address_value;
            } else if(isdigit(c)) {
                FSM_token = FSM_token_states::Number;
                type = Token_t::Number_value;
            } else {
                // Invalid character, error
                throw Conf_file_syntax_exception();
            }
            value += c;
        } else if(FSM_token == FSM_token_states::Text) {
            // Text token
            value += c;
            if(c == '\'') {
                return true;
            }
        } else if(FSM_token == FSM_token_states::Address) {
            // Address token
            if((value == "0" && (c == 'x' || c == 'X')) || (value.length() > 1 && isxdigit(c))) {
                value += c;
            } else {
                position--;
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
        } else {
            // Magic code token
            if(c == 'C' || c == 'I') {
                value += c;
            } else if(value == "CCICC") {
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

void Configuration::Parse_filter() {
    Token_t tok_type;
    std::string tok_val;
    void *func_p;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Br_square_begin, tok_val);

    // Traverse the collection
    while(1) {
        Test_next_token_type(Token_t::Address_value, tok_val);
        // Convert to the pointer
        Address_token_to_pointer(tok_val, &func_p);

        // Try to find the function configuration record
        auto func_record = func_config.find(func_p);
        if(func_record != func_config.end()) {
            // Function already has a configuration record, update
            std::get<filter>(func_record->second) = true;
        } else {
            // Function does not have a configuration record yet, create one
            func_config.insert({func_p, std::make_tuple(filter_on, sample_off, sample_init, sample_init)});
        }

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
    int sample_val;

    Test_next_token_type(Token_t::Op_colon, tok_val);
    Test_next_token_type(Token_t::Br_square_begin, tok_val);
    // Traverse the collection
    while(1) {
        // { 'func' : address, 'sample': number },
        Test_next_token_type(Token_t::Br_curly_begin, tok_val);
        Test_next_token_type(Token_t::Text_value, tok_val);
        Test_token_val("'func'", tok_val);
        Test_next_token_type(Token_t::Op_colon, tok_val);
        Test_next_token_type(Token_t::Address_value, tok_val);
        // Convert the address to a pointer
        Address_token_to_pointer(tok_val, &func_p);
        Test_next_token_type(Token_t::Comma, tok_val);
        Test_next_token_type(Token_t::Text_value, tok_val);
        Test_token_val("'sample'", tok_val);
        Test_next_token_type(Token_t::Op_colon, tok_val);
        Test_next_token_type(Token_t::Number_value, tok_val);
        // Convert the sample to a integer
        sample_val = std::stoi(tok_val);

        // Search for the function configuration record
        auto func_record = func_config.find(func_p);
        if(func_record != func_config.end()) {
            // Function already has a configuration record, update
            std::get<sample>(func_record->second) = true;
        } else {
            // Function does not have a configuration record yet, create one
            func_config.insert({func_p, std::make_tuple(filter_off, sample_on, sample_val-1, sample_val)});
        }
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
    if(sscanf(address.c_str(), "0x%p", addr) != 1) {
        // Conversion to a pointer failed
        throw Conf_file_syntax_exception();
    }
}
