// C++17 starter agent: a small but functional greedy collector.
//
// Copy this file and change decide(). Each ship walks to the nearest
// worthwhile deposit, mines while the cell is rich enough and brings the
// cargo home. Diagnostics go to stderr; stdout carries only the protocol.
#include "neon_agent_kit.hpp"

#include <set>
#include <string>
#include <vector>

namespace {

constexpr int MIN_WORTH = 20;    // cells at or below this energy are skipped
constexpr int RETURN_CARGO = 50; // go home instead of to another deposit

neon::Position choose_goal(const neon::Game& game, const neon::TickState& state,
                           const neon::Ship& ship, std::set<neon::Position>& taken) {
    const neon::Position here = ship.pos();
    const std::vector<int> distances = game.distances_from(here);
    const int home_distance = distances[game.index(game.my_base)];
    const int ticks_left = game.max_ticks - state.tick + 1;
    const int limit = ticks_left < state.my_budget ? ticks_left : state.my_budget;
    const bool running_out = limit <= home_distance + 2;

    if (ship.cargo >= neon::SHIP_CAPACITY || (ship.cargo > 0 && running_out)) {
        return game.my_base;
    }
    const int energy_here = state.energy_at(here);
    if (energy_here > MIN_WORTH) {
        return here; // keep mining
    }
    if (ship.cargo >= RETURN_CARGO) {
        return game.my_base;
    }
    bool found = false;
    neon::Position best;
    int best_distance = 0;
    for (const auto& cell : state.energy) { // row-major order, so ties are stable
        const int distance = distances[game.index(cell.first)];
        if (cell.second <= MIN_WORTH || distance < 0 || taken.count(cell.first) != 0) {
            continue;
        }
        if (!found || distance < best_distance) {
            found = true;
            best = cell.first;
            best_distance = distance;
        }
    }
    if (found) {
        taken.insert(best);
        return best;
    }
    if (energy_here > 0) {
        return here;
    }
    return ship.cargo > 0 ? game.my_base : here;
}

neon::Commands decide(const neon::Game& game, const neon::TickState& state) {
    neon::Commands commands;
    int budget = state.my_budget;
    std::set<neon::Position> occupied;
    for (const auto& ship : state.ships) {
        occupied.insert(ship.pos());
    }
    std::set<neon::Position> reserved;
    std::set<neon::Position> taken;
    for (const auto& ship : state.my_ships) {
        const neon::Position goal = choose_goal(game, state, ship, taken);
        std::string action = "STAY";
        if (goal != ship.pos() && budget > 0) {
            std::set<neon::Position> avoid = occupied;
            avoid.erase(ship.pos());
            avoid.insert(reserved.begin(), reserved.end());
            avoid.erase(game.my_base); // own ships may share the base
            action = game.step_towards(ship.pos(), goal, avoid);
        }
        if (action != "STAY") {
            --budget;
        }
        reserved.insert(neon::apply_action(ship.pos(), action));
        commands.move(ship.id, action);
    }
    return commands;
}

} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    return neon::run(decide);
}
