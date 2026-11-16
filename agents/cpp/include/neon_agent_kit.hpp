// Neon Armada agent starter kit for C++17 (protocol version 1).
//
// Header-only and dependency-free. An agent is an independent program that
// talks to the engine through stdin/stdout as described in
// contracts/agent-protocol.md. stdout is reserved for protocol messages (the
// kit writes them); write diagnostics to std::cerr.
//
// Minimal agent:
//
//   #include "neon_agent_kit.hpp"
//   int main() {
//       return neon::run([](const neon::Game&, const neon::TickState& state) {
//           neon::Commands commands;
//           for (const auto& ship : state.my_ships) commands.move(ship.id, "STAY");
//           return commands;
//       });
//   }
#pragma once

#include <cstddef>
#include <deque>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace neon {

constexpr int PROTOCOL_VERSION = 1;
constexpr int SHIP_CAPACITY = 100;
constexpr int BUILD_COST = 500;

// ---------------------------------------------------------------- JSON ----

// Minimal JSON value: enough for the integer-only protocol messages.
struct Json {
    enum class Type { Null, Bool, Int, String, Array, Object };

    Type type = Type::Null;
    bool boolean = false;
    long long integer = 0;
    std::string text;
    std::vector<Json> items;
    std::vector<std::pair<std::string, Json>> members;

    const Json* find(const std::string& key) const {
        for (const auto& member : members) {
            if (member.first == key) {
                return &member.second;
            }
        }
        return nullptr;
    }

    const Json& at(const std::string& key) const {
        const Json* value = find(key);
        if (value == nullptr) {
            throw std::runtime_error("missing key: " + key);
        }
        return *value;
    }

    int as_int() const {
        if (type != Type::Int) {
            throw std::runtime_error("expected an integer");
        }
        return static_cast<int>(integer);
    }

    bool as_bool() const {
        if (type != Type::Bool) {
            throw std::runtime_error("expected a boolean");
        }
        return boolean;
    }

    const std::string& as_string() const {
        if (type != Type::String) {
            throw std::runtime_error("expected a string");
        }
        return text;
    }

    const std::vector<Json>& as_array() const {
        if (type != Type::Array) {
            throw std::runtime_error("expected an array");
        }
        return items;
    }
};

class JsonParser {
  public:
    explicit JsonParser(const std::string& input) : input_(input) {}

    Json parse() {
        Json value = parse_value();
        skip_whitespace();
        if (position_ != input_.size()) {
            throw std::runtime_error("unexpected trailing characters");
        }
        return value;
    }

  private:
    const std::string& input_;
    std::size_t position_ = 0;

    void skip_whitespace() {
        while (position_ < input_.size()) {
            const char c = input_[position_];
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
                break;
            }
            ++position_;
        }
    }

    char peek() {
        skip_whitespace();
        if (position_ >= input_.size()) {
            throw std::runtime_error("unexpected end of input");
        }
        return input_[position_];
    }

    void expect(char expected) {
        if (peek() != expected) {
            throw std::runtime_error(std::string("expected '") + expected + "'");
        }
        ++position_;
    }

    bool consume_literal(const std::string& literal) {
        if (input_.compare(position_, literal.size(), literal) == 0) {
            position_ += literal.size();
            return true;
        }
        return false;
    }

    Json parse_value() {
        const char c = peek();
        Json value;
        if (c == '{') {
            value.type = Json::Type::Object;
            ++position_;
            if (peek() == '}') {
                ++position_;
                return value;
            }
            while (true) {
                std::string key = parse_string();
                expect(':');
                value.members.emplace_back(std::move(key), parse_value());
                if (peek() == ',') {
                    ++position_;
                    continue;
                }
                expect('}');
                return value;
            }
        }
        if (c == '[') {
            value.type = Json::Type::Array;
            ++position_;
            if (peek() == ']') {
                ++position_;
                return value;
            }
            while (true) {
                value.items.push_back(parse_value());
                if (peek() == ',') {
                    ++position_;
                    continue;
                }
                expect(']');
                return value;
            }
        }
        if (c == '"') {
            value.type = Json::Type::String;
            value.text = parse_string();
            return value;
        }
        if (consume_literal("true")) {
            value.type = Json::Type::Bool;
            value.boolean = true;
            return value;
        }
        if (consume_literal("false")) {
            value.type = Json::Type::Bool;
            return value;
        }
        if (consume_literal("null")) {
            return value;
        }
        return parse_integer();
    }

    Json parse_integer() {
        const std::size_t start = position_;
        if (position_ < input_.size() && input_[position_] == '-') {
            ++position_;
        }
        while (position_ < input_.size() && input_[position_] >= '0' &&
               input_[position_] <= '9') {
            ++position_;
        }
        if (position_ == start ||
            (position_ < input_.size() &&
             (input_[position_] == '.' || input_[position_] == 'e' ||
              input_[position_] == 'E'))) {
            throw std::runtime_error("only integers are supported");
        }
        Json value;
        value.type = Json::Type::Int;
        value.integer = std::stoll(input_.substr(start, position_ - start));
        return value;
    }

    std::string parse_string() {
        expect('"');
        std::string result;
        while (true) {
            if (position_ >= input_.size()) {
                throw std::runtime_error("unterminated string");
            }
            const char c = input_[position_++];
            if (c == '"') {
                return result;
            }
            if (c != '\\') {
                result.push_back(c);
                continue;
            }
            if (position_ >= input_.size()) {
                throw std::runtime_error("unterminated escape");
            }
            const char escape = input_[position_++];
            switch (escape) {
            case 'n':
                result.push_back('\n');
                break;
            case 't':
                result.push_back('\t');
                break;
            case 'r':
                result.push_back('\r');
                break;
            case 'b':
                result.push_back('\b');
                break;
            case 'f':
                result.push_back('\f');
                break;
            case 'u':
                // Protocol strings are ASCII; keep a placeholder for others.
                if (position_ + 4 > input_.size()) {
                    throw std::runtime_error("bad unicode escape");
                }
                position_ += 4;
                result.push_back('?');
                break;
            default:
                result.push_back(escape);
                break;
            }
        }
    }
};

inline Json parse_json(const std::string& input) {
    return JsonParser(input).parse();
}

// ---------------------------------------------------------------- game ----

struct Position {
    int x = 0;
    int y = 0;

    bool operator==(const Position& other) const {
        return x == other.x && y == other.y;
    }
    bool operator!=(const Position& other) const {
        return !(*this == other);
    }
    // Row-major order: y first, then x.
    bool operator<(const Position& other) const {
        return y != other.y ? y < other.y : x < other.x;
    }
};

struct Ship {
    int id = 0;
    int owner = 0;
    int x = 0;
    int y = 0;
    int cargo = 0;

    Position pos() const {
        return Position{x, y};
    }
};

inline Position apply_action(const Position& from, const std::string& action) {
    if (action == "N")
        return Position{from.x, from.y - 1};
    if (action == "S")
        return Position{from.x, from.y + 1};
    if (action == "E")
        return Position{from.x + 1, from.y};
    if (action == "W")
        return Position{from.x - 1, from.y};
    return from;
}

// Static match data from the init message plus path-finding helpers.
class Game {
  public:
    int player_id = 0;
    int size = 0;
    int max_ticks = 0;
    std::vector<std::string> cells;
    Position my_base;
    Position enemy_base;

    explicit Game(const Json& message) {
        player_id = message.at("player_id").as_int();
        max_ticks = message.at("config").at("max_ticks").as_int();
        const Json& map = message.at("map");
        size = map.at("size").as_int();
        for (const Json& row : map.at("cells").as_array()) {
            cells.push_back(row.as_string());
        }
        const auto& bases = map.at("bases").as_array();
        const auto base_of = [&bases](int player) {
            const auto& pair = bases.at(static_cast<std::size_t>(player)).as_array();
            return Position{pair.at(0).as_int(), pair.at(1).as_int()};
        };
        my_base = base_of(player_id);
        enemy_base = base_of(1 - player_id);
    }

    bool in_bounds(int x, int y) const {
        return x >= 0 && y >= 0 && x < size && y < size;
    }

    // True if my ships may enter the cell (no obstacle, not the enemy base).
    bool passable(int x, int y) const {
        if (!in_bounds(x, y)) {
            return false;
        }
        const char kind =
            cells[static_cast<std::size_t>(y)][static_cast<std::size_t>(x)];
        return kind != '#' && !(x == enemy_base.x && y == enemy_base.y);
    }

    // Breadth-first distances from origin, indexed by y * size + x; -1 = unreachable.
    std::vector<int> distances_from(const Position& origin) const {
        std::vector<int> distances(static_cast<std::size_t>(size * size), -1);
        std::deque<Position> queue;
        distances[index(origin)] = 0;
        queue.push_back(origin);
        static const int DX[4] = {0, 0, 1, -1};
        static const int DY[4] = {-1, 1, 0, 0};
        while (!queue.empty()) {
            const Position current = queue.front();
            queue.pop_front();
            for (int direction = 0; direction < 4; ++direction) {
                const Position next{current.x + DX[direction],
                                    current.y + DY[direction]};
                if (passable(next.x, next.y) && distances[index(next)] < 0) {
                    distances[index(next)] = distances[index(current)] + 1;
                    queue.push_back(next);
                }
            }
        }
        return distances;
    }

    // Action that brings start one step closer to goal without entering a
    // cell in avoid; "STAY" if there is none.
    std::string step_towards(const Position& start, const Position& goal,
                             const std::set<Position>& avoid) const {
        if (start == goal) {
            return "STAY";
        }
        const std::vector<int> distances = distances_from(goal);
        int best = distances[index(start)];
        if (best < 0) {
            return "STAY";
        }
        std::string best_action = "STAY";
        static const char* const NAMES[4] = {"N", "S", "E", "W"};
        for (const char* name : NAMES) {
            const Position next = apply_action(start, name);
            if (!in_bounds(next.x, next.y) || avoid.count(next) != 0) {
                continue;
            }
            const int candidate = distances[index(next)];
            if (candidate >= 0 && candidate < best) {
                best = candidate;
                best_action = name;
            }
        }
        return best_action;
    }

    std::size_t index(const Position& position) const {
        return static_cast<std::size_t>(position.y * size + position.x);
    }
};

// Dynamic state from one tick message.
struct TickState {
    int tick = 0;
    int my_reserve = 0;
    int my_budget = 0;
    bool my_pending_build = false;
    std::vector<Ship> ships;
    std::vector<Ship> my_ships;
    std::vector<Ship> enemy_ships;
    std::map<Position, int> energy; // row-major iteration order

    TickState(const Json& message, int player_id) {
        const auto player = static_cast<std::size_t>(player_id);
        tick = message.at("tick").as_int();
        my_reserve = message.at("reserves").as_array().at(player).as_int();
        my_budget = message.at("move_budgets").as_array().at(player).as_int();
        my_pending_build = message.at("pending_builds").as_array().at(player).as_bool();
        for (const Json& item : message.at("ships").as_array()) {
            Ship ship;
            ship.id = item.at("id").as_int();
            ship.owner = item.at("owner").as_int();
            ship.x = item.at("x").as_int();
            ship.y = item.at("y").as_int();
            ship.cargo = item.at("cargo").as_int();
            ships.push_back(ship);
            (ship.owner == player_id ? my_ships : enemy_ships).push_back(ship);
        }
        for (const Json& item : message.at("energy").as_array()) {
            const auto& triple = item.as_array();
            energy[Position{triple.at(0).as_int(), triple.at(1).as_int()}] =
                triple.at(2).as_int();
        }
    }

    int energy_at(const Position& position) const {
        const auto found = energy.find(position);
        return found == energy.end() ? 0 : found->second;
    }
};

// Commands of one tick: at most one action per ship and one build request.
class Commands {
  public:
    void move(int ship_id, const std::string& action) {
        moves_[ship_id] = action;
    }
    void request_build() {
        build_ = true;
    }

    std::string to_json(int tick) const {
        std::string out =
            "{\"type\":\"commands\",\"tick\":" + std::to_string(tick) + ",\"moves\":[";
        bool first = true;
        for (const auto& move : moves_) {
            if (!first) {
                out += ",";
            }
            first = false;
            out += "{\"ship\":" + std::to_string(move.first) + ",\"action\":\"" +
                   move.second + "\"}";
        }
        out += std::string("],\"build\":") + (build_ ? "true" : "false") + "}";
        return out;
    }

  private:
    std::map<int, std::string> moves_;
    bool build_ = false;
};

using DecideFunction = std::function<Commands(const Game&, const TickState&)>;

// Runs the protocol loop until "end" or end of input; returns an exit code.
inline int run(const DecideFunction& decide, std::istream& in = std::cin,
               std::ostream& out = std::cout) {
    std::unique_ptr<Game> game;
    std::string line;
    while (std::getline(in, line)) {
        if (line.find_first_not_of(" \t\r\n") == std::string::npos) {
            continue;
        }
        try {
            const Json message = parse_json(line);
            const std::string& type = message.at("type").as_string();
            if (type == "init") {
                if (message.at("protocol_version").as_int() != PROTOCOL_VERSION) {
                    std::cerr << "neon_agent_kit: unsupported protocol version\n";
                    return 1;
                }
                game = std::make_unique<Game>(message);
                out << "{\"type\":\"ready\",\"protocol_version\":" << PROTOCOL_VERSION
                    << "}\n"
                    << std::flush;
            } else if (type == "tick") {
                if (!game) {
                    std::cerr << "neon_agent_kit: tick received before init\n";
                    return 1;
                }
                const TickState state(message, game->player_id);
                Commands commands;
                try {
                    commands = decide(*game, state);
                } catch (const std::exception& error) {
                    // Keep playing after a strategy bug: send no commands.
                    std::cerr << "neon_agent_kit: decide failed: " << error.what()
                              << "\n";
                    commands = Commands();
                }
                out << commands.to_json(state.tick) << "\n" << std::flush;
            } else if (type == "end") {
                return 0;
            } else {
                std::cerr << "neon_agent_kit: unknown message type\n";
                return 1;
            }
        } catch (const std::exception& error) {
            std::cerr << "neon_agent_kit: malformed message: " << error.what() << "\n";
            return 1;
        }
    }
    return 0;
}

} // namespace neon
