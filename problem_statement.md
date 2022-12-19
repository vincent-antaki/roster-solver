# Events Scheduling Problem

## Summary

This repo implements looks for a good solutions for an event schedule problem; it takes a pool of workers and a list of events and assigns them according of a set of constraints. The constraints include location the workers are willing/able to go, skill the event required, priority in assigning the workers based on status.


## Problem statement

### Sets

- $E$: the sets of events
- $L$: the sets of locations where events take place
- $T$: the sets of timeperiod where events take place
- $P$: the sets of workers

### Parameters

For events:
  - $L_{el}$ indicates whether event $e$ is happening at location $l$
  - $P_{ed}$ indicates wheter the event $e$ is happening during timeperiod $d$
  - $N_e$ indicates the amount of worker needed at an event


For workers:
  - $M_{p}, F_{p}, C_p$ : Whether person p has mech, first aid and leader training
  - $G_{pl}$ indicates whether person $p$ is willing to go at location $l$
  - $R_{pl}$ indicates whether person $p$ is considered very close to location $l$
  - $A_{pd}$ indicates whether person $p$ is willing to work on timeperiod $d$


### Variables
- $S_{pe}$: indicates whether person $p$ is scheduled to work at event $e$
    - $S_{pe}$ variable will only be instanciaded where $G_{pl}$ and $A_{pd}$ allows it.
- $z$: score indicating how inconvenient a schedule is.

### Objective

- Set $S_{pe}$ which respect constraints
#- Minimize $z$

### Constraints

1.  Every events has the required amount of workers
$$
\forall e \in E,\  \sum_{p \in P} S_{pe} = N_e
$$

2. Workers can't be scheduled at the events at the same time

$$
	\forall e_1, e_2 \in (E, E),\  \sum_{p \in P}S_{pe_1}S_{pe_2} = 0
$$

3. Every events have 2 workers which have mech training, 2 with first aid training, and one with leader training
$$
\forall e \in E,\  \sum_{p \in P} S_{pe} M_p \geq 2, \sum_{p \in P} S_{pe} F_p \geq 2, \sum_{p \in P} S_{pe} C_p \geq 1
$$

### Inconvinience functions

1. Prioritize worker assignment in function of priority level
2. For a given event set, prioritize the same team assignment
3. Prioritize Prioriser les gens dans leur quartier de résidence
4. pro rata de masse d'heure entre les gens du même level
5. Prioriser la même équipe pour l'école.

### Assumptions

- Time to get between locations is negligible
- Even if a worker is scheduled for the whole week (without being double booked), his schedule will not exceed the maximum planned number of hours.