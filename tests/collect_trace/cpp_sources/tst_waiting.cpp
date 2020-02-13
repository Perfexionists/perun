#include <chrono>
#include <thread>
#include <iostream>

int main() {
    std::cout << "C++ waiting" << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(3));
    std::cout << "C++ waiting finished" << std::endl;

    return 0;
}
