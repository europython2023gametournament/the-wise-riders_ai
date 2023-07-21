# SPDX-License-Identifier: BSD-3-Clause

import numpy as np

# This is your team name
CREATOR = "The Wise Riders"


# This is the AI bot that will be instantiated for the competition
class PlayerAi:
    def __init__(self):
        self.team = CREATOR  # Mandatory attribute

        # Record the previous positions of all my vehicles
        self.previous_positions = {}
        # Record the number of tanks and ships I have at each base
        self.ntanks = {}
        self.nships = {}

    def run(self, t: float, dt: float, info: dict, game_map: np.ndarray):
        """
        This is the main function that will be called by the game engine.

        Parameters
        ----------
        t : float
            The current time in seconds.
        dt : float
            The time step in seconds.
        info : dict
            A dictionary containing all the information about the game.
            The structure is as follows:
            {
                "team_name_1": {
                    "bases": [base_1, base_2, ...],
                    "tanks": [tank_1, tank_2, ...],
                    "ships": [ship_1, ship_2, ...],
                    "jets": [jet_1, jet_2, ...],
                },
                "team_name_2": {
                    ...
                },
                ...
            }
        game_map : np.ndarray
            A 2D numpy array containing the game map.
            1 means land, 0 means water, -1 means no info.
        """
        if t < 180: # 3 minutes
            self.strategy_early(info=info)
        elif t < 360: # 6 minutes
            self.strategy_midgame(info=info)
        else:
            self.strategy_lategame(info=info)
            
        myinfo = info[self.team]
        # Try to find an enemy target
        target = None
        # If there are multiple teams in the info, find the first team that is not mine
        if len(info) > 1:
            for name in info:
                if name != self.team:
                    # Target only bases
                    if "bases" in info[name]:
                        # Simply target the first base
                        t = info[name]["bases"][0]
                        target = [t.x, t.y]

        # Controlling my vehicles ==============================================

        # Iterate through all my tanks
        if "tanks" in myinfo:
            for tank in myinfo["tanks"]:
                tank_target = None
                bases = [base for name in info for base in info[name].get('bases', []) if name != self.team]
                nearest_base = None
                nearest_base = sorted(bases, key=lambda b: (b.x - tank.x) ** 2 + (b.y - tank.y) ** 2)
                if nearest_base:
                    tank_target = nearest_base[0]
                if (tank.uid in self.previous_positions) and (not tank.stopped):
                    # If the tank position is the same as the previous position,
                    # set a random heading
                    if all(tank.position == self.previous_positions[tank.uid]):
                        tank.set_heading(np.random.random() * 360.0)
                    # Else, if there is a target, go to the target
                    elif tank_target is not None:
                        try:
                            tank.goto(*tank_target)
                        except Exception:
                            pass
                # Store the previous position of this tank for the next time step
                self.previous_positions[tank.uid] = tank.position

        # Iterate through all my ships
        if "ships" in myinfo:
            for ship in myinfo["ships"]:
                if ship.uid in self.previous_positions:
                    # If the ship position is the same as the previous position,
                    # convert the ship to a base if it is far from the owning base,
                    # set a random heading otherwise
                    if all(ship.position == self.previous_positions[ship.uid]):
                        if ship.get_distance(ship.owner.x, ship.owner.y) > 20:
                            ship.convert_to_base()
                        else:
                            ship.set_heading(np.random.random() * 360.0)
                # Store the previous position of this ship for the next time step
                self.previous_positions[ship.uid] = ship.position

        target = None
        # If there are multiple teams in the info, find the first team that is not mine
        def determine_base_power(base):
            return base.mines * 10 + base.crystal/10

        def determine_power(team):
            return 100 * len(team.get('bases', [])) + sum(determine_base_power(base) for base in team.get('bases', []))

        if len(info) > 1:
            teams = [team for name, team in info.items() if name != self.team]
            by_power = sorted(teams, key=determine_power)
            if by_power:
                strongest_enemy = by_power[-1]
                if not 'bases' in strongest_enemy:
                    target = [75,75]
                else:
                    strongest_base = sorted(strongest_enemy.get('bases', []), key=determine_base_power)
                    if not strongest_base:
                        target = [75,75]
                    else:
                        strongest_base = strongest_base[-1]
                        target = [strongest_base.x, strongest_base.y]

        # Iterate through all my jets
        if "jets" in myinfo:
            for jet in myinfo["jets"]:
                # Jets simply go to the target if there is one, they never get stuck
                if target is not None:
                    jet.goto(*target)


    def strategy_early(self, info):
        # Get information about my team
        myinfo = info[self.team]
        max_ships_per_base = 6
        max_mines_per_base = 3
        # Controlling my bases =================================================

        # Iterate through all my bases (vehicles belong to bases)
        for base in myinfo["bases"]:
            # If this is a new base, initialize the tank & ship counters
            if base.uid not in self.ntanks:
                self.ntanks[base.uid] = 0
            if base.uid not in self.nships:
                self.nships[base.uid] = 0
            # Firstly, each base should build a mine if it has less than 3 mines
            if base.mines < max_mines_per_base:
                if base.crystal > base.cost("mine"):
                    base.build_mine()
            elif base.crystal > base.cost("tank") and self.ntanks[base.uid] < 2:
                # build_tank() returns the uid of the tank that was built
                tank_uid = base.build_tank(heading=360 * np.random.random())
                # Add 1 to the tank counter for this base
                self.ntanks[base.uid] += 1
            # Thirdly, each base should build a ship if it has less than 3 ships
            elif base.crystal > base.cost("ship") and self.nships[base.uid] < max_ships_per_base:
                # build_ship() returns the uid of the ship that was built
                ship_uid = base.build_ship(heading=360 * np.random.random())
                # Add 1 to the ship counter for this base
                self.nships[base.uid] += 1
            # Secondly, each base should build a tank if it has less than 5 tanks
            elif base.crystal > base.cost("tank") and self.ntanks[base.uid] < 5 and self.nships[base.uid] >= max_ships_per_base:
                # build_tank() returns the uid of the tank that was built
                tank_uid = base.build_tank(heading=360 * np.random.random())
                # Add 1 to the tank counter for this base
                self.ntanks[base.uid] += 1
            # If everything else is satisfied, build a jet
            elif base.crystal > base.cost("jet"):
                # build_jet() returns the uid of the jet that was built
                jet_uid = base.build_jet(heading=360 * np.random.random())

    def strategy_midgame(self, info):
            # Get information about my team
            myinfo = info[self.team]

            # Controlling my bases =================================================

            # Iterate through all my bases (vehicles belong to bases)
            for base in myinfo["bases"]:
                # If this is a new base, initialize the tank & ship counters
                if base.uid not in self.ntanks:
                    self.ntanks[base.uid] = 0
                if base.uid not in self.nships:
                    self.nships[base.uid] = 0
                # Firstly, each base should build a mine if it has less than 3 mines
                if base.mines < 2:
                    if base.crystal > base.cost("mine"):
                        base.build_mine()
                elif base.crystal > base.cost("tank") and self.ntanks[base.uid] < 2:
                    # build_tank() returns the uid of the tank that was built
                    tank_uid = base.build_tank(heading=360 * np.random.random())
                    # Add 1 to the tank counter for this base
                    self.ntanks[base.uid] += 1
                # Thirdly, each base should build a ship if it has less than 3 ships
                elif base.crystal > base.cost("ship") and self.nships[base.uid] < 2:
                    # build_ship() returns the uid of the ship that was built
                    ship_uid = base.build_ship(heading=360 * np.random.random())
                    # Add 1 to the ship counter for this base
                    self.nships[base.uid] += 1
                # Secondly, each base should build a tank if it has less than 5 tanks
                # If everything else is satisfied, build a jet
                elif base.crystal > base.cost("jet"):
                    # build_jet() returns the uid of the jet that was built
                    jet_uid = base.build_jet(heading=360 * np.random.random())



    def strategy_lategame(self, info):
            # Get information about my team
            myinfo = info[self.team]

            # Controlling my bases =================================================

            # Iterate through all my bases (vehicles belong to bases)
            for base in myinfo["bases"]:
                # If this is a new base, initialize the tank & ship counters
                if base.uid not in self.ntanks:
                    self.ntanks[base.uid] = 0
                if base.uid not in self.nships:
                    self.nships[base.uid] = 0
                # If everything else is satisfied, build a jet
                if base.crystal > base.cost("jet"):
                    # build_jet() returns the uid of the jet that was built
                    jet_uid = base.build_jet(heading=360 * np.random.random())

