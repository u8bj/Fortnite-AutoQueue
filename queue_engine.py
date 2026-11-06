"""Pure state machine consuming temporally confirmed visual cue names.

These semantic inputs are an evidence contract, not an image classifier. In
particular, ``placement`` must recognize the stable placement heading rather
than a particular number, and ``teammate_alive`` must identify a living player
on our team. Team-end proof requires explicit ``team_eliminated`` plus either
``placement`` or ``match_summary``. A personal summary and placement alone
never prove team elimination. Conflicting live/lobby/loading cues revoke proof
and suppress inputs until fresh unambiguous evidence arrives. Current own-death
or spectating cues also veto result actions and revoke any retained team proof.
Synthetic cue
sequences cannot establish live detector accuracy.
Actions are intentions: the runtime must independently recheck foreground and
stop status immediately before input, and call fail() if execution fails.
Unknown screens remain in DETECTING without a deadline. Transient errors and
resume use fresh visual synchronization, preserving consumed action flags and
rounds. Only action_cancelled() may release a flag when the adapter guarantees
that no event was sent; exceptions retain flags because input may have occurred.
After proven team elimination, the only final action is ``return_lobby``.
Its consumed flag survives recovery until genuine lobby+play evidence appears.
Loading or bus cues while returning never start another queue or send Space.
"""
from enum import Enum
import math


class State(str, Enum):
    DETECTING = "DETECTING"
    LOBBY = "LOBBY"
    MATCHMAKING = "MATCHMAKING"
    LOADING = "LOADING"
    BATTLE_BUS = "BATTLE_BUS"
    JUMPING = "JUMPING"
    IN_MATCH = "IN_MATCH"
    SPECTATING = "SPECTATING"
    TEAM_ELIMINATED = "TEAM_ELIMINATED"
    WAITING_FOR_RESULTS = "WAITING_FOR_RESULTS"
    SKIP_XP = "SKIP_XP"
    MATCH_SUMMARY = "MATCH_SUMMARY"
    RETURNING_TO_LOBBY = "RETURNING_TO_LOBBY"
    ERROR = "ERROR"


class Engine:
    """Issue each action at most once until visibly confirmed next round.

    ``now`` is a caller-provided monotonic timestamp in seconds. Timeouts use
    state names (upper or lower case) and positive finite seconds. Focus loss
    pauses deadlines. No timeout provides proof of death or allows an input.
    """
    DEFAULT_TIMEOUTS = {
        "LOBBY": 120, "MATCHMAKING": 600, "LOADING": 600,
        "BATTLE_BUS": 120, "JUMPING": 15, "IN_MATCH": 7200,
        "SPECTATING": 7200, "TEAM_ELIMINATED": 180,
        "WAITING_FOR_RESULTS": 180, "SKIP_XP": 180,
        "MATCH_SUMMARY": 180, "RETURNING_TO_LOBBY": 300,
        "REPLAY": 300,  # Legacy configuration key; no replay action/state.
    }
    RESULT_STATES = frozenset({State.TEAM_ELIMINATED,
                              State.WAITING_FOR_RESULTS, State.SKIP_XP,
                              State.MATCH_SUMMARY})

    def __init__(self, timeouts: dict | None = None):
        self.timeouts = self.DEFAULT_TIMEOUTS.copy()
        for key, value in (timeouts or {}).items():
            name = str(key.value if isinstance(key, State) else key).upper()
            if name not in self.timeouts:
                raise ValueError(f"Unknown timeout state: {key}")
            seconds = float(value)
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError(f"Timeout for {name} must be positive and finite")
            self.timeouts[name] = seconds
        self.reset()

    def reset(self, now=0):
        self.state = State.DETECTING
        self.rounds = 0
        self.last_action = ""
        self.error = ""
        self.entered_at = now
        self._ready_sent = False
        self._jump_sent = False
        self._skip_sent = False
        self._return_sent = False
        self._round_counted = False
        self._team_end = False
        self._continue_at = None
        self._paused_at = None
        self._resuming = False
        self._resume_origin = State.DETECTING
        self._revive_streak = 0
        self._awaiting_ready = False

    def fail(self, message, now):
        self._revive_streak = 0
        if self.state not in {State.ERROR, State.DETECTING}:
            self._resume_origin = self.state
        self.error = str(message)
        self._team_end = False
        self._continue_at = None
        self._enter(State.ERROR, now)

    def resume(self, now):
        """Re-synchronize visually without forgetting consumed input actions.

        Rounds and one-shot flags survive stop/start or transient errors. Only
        a positively identified new lobby/round can clear previous round flags.
        Recovery never authorizes an input on its synchronization frame.
        """
        if self.state not in {State.ERROR, State.DETECTING}:
            self._resume_origin = self.state
        self._team_end = False
        self._continue_at = None
        self._paused_at = None
        self._resuming = True
        self._revive_streak = 0
        self._enter(State.DETECTING, now)

    @staticmethod
    def _bus_visible(visible):
        return "jump" in visible and not visible & {
            "own_dead", "spectating", "placement", "team_eliminated",
            "match_summary", "lobby", "play", "loading", "matchmaking",
            "in_match", "falling", "glider", "continue", "skip", "replay", "return_lobby"}

    @staticmethod
    def _lobby_visible(visible):
        return {"lobby", "play"} <= visible and not visible & {
            "own_dead", "spectating", "teammate_alive", "team_eliminated",
            "placement", "match_summary", "continue", "skip", "replay",
            "return_lobby", "loading", "matchmaking", "jump", "in_match",
            "falling", "glider"}

    def _arrived_in_lobby(self, now):
        self._new_round()
        self._ready_sent = False
        self._awaiting_ready = True
        self._resume_origin = State.LOBBY
        self._enter(State.LOBBY, now)
        self.error = ""

    def _synchronize(self, visible, now):
        """Identify actual screen from confirmed cues; unknown stays passive."""
        if self._return_sent:
            if not self._lobby_visible(visible):
                return False
            self._arrived_in_lobby(now)
            return True
        if self._awaiting_ready and not self._lobby_visible(visible):
            return False
        terminal = "team_eliminated" in visible and bool(
            visible & {"placement", "match_summary"})
        conflict = visible & {"lobby", "play", "matchmaking", "loading",
                              "jump", "in_match", "falling", "glider", "teammate_alive"}
        if visible & {"spectating", "own_dead"}:
            state = State.SPECTATING
        elif terminal and conflict:
            return False
        elif visible & {"in_match", "falling", "glider"}:
            state = State.IN_MATCH
        elif self._bus_visible(visible):
            state = State.IN_MATCH if self._jump_sent else State.BATTLE_BUS
        elif "loading" in visible:
            state = State.LOADING
        elif "matchmaking" in visible:
            state = State.MATCHMAKING
        elif {"lobby", "play"} <= visible:
            state = State.LOBBY
        elif terminal:
            state = State.TEAM_ELIMINATED
        else:
            return False

        active_origin = self._resume_origin not in {
            State.DETECTING, State.LOBBY, State.ERROR}
        if state == State.LOBBY and active_origin:
            self._new_round()
            self._ready_sent = False
            self._awaiting_ready = True
        if state in {State.MATCHMAKING, State.LOADING, State.BATTLE_BUS}:
            self._count_round()
        self._team_end = state == State.TEAM_ELIMINATED
        self._enter(state, now)
        self.error = ""
        return True

    def action_succeeded(self, action, now):
        """The input adapter completed Space; no falling/glider cue is required.

        This acknowledges the key event, not a separately verified physical jump.
        Failed/blocked inputs must call fail() instead. Do not resend Space.
        """
        if action == 'jump' and self.state == State.JUMPING and self._jump_sent:
            self._enter(State.IN_MATCH, now)

    def action_cancelled(self, action, now):
        """Release one flag ONLY when the adapter guarantees no input was sent.

        Focus/target loss before dispatch is safe to retry after synchronization.
        For an exception after possible dispatch use fail(), preserving all flags.
        """
        flags = {"ready": "_ready_sent", "jump": "_jump_sent",
                 "skip": "_skip_sent", "return_lobby": "_return_sent"}
        if action not in flags:
            raise ValueError(f"Unknown action: {action}")
        setattr(self, flags[action], False)
        if action == "ready":
            self._awaiting_ready = True
        self.error = f"{action} cancelled before input; waiting for fresh visual evidence"
        self.resume(now)

    def _enter(self, state, now):
        if self.state != state:
            self._revive_streak = 0
            self.state = state
            self.entered_at = now

    def _action(self, name):
        self.last_action = name
        return [name]

    def _count_round(self):
        if not self._round_counted:
            self.rounds += 1
            self._round_counted = True

    def _new_round(self):
        self._round_counted = False
        self._jump_sent = False
        self._skip_sent = False
        self._return_sent = False
        self._team_end = False
        self._continue_at = None

    def step(self, visible: set[str], now: float, focused: bool = True,
             mode_ok: bool = True) -> list[str]:
        if not focused:
            self._revive_streak = 0
            if self._paused_at is None:
                self._paused_at = now
            return []
        if self._paused_at is not None:
            duration = max(0, now - self._paused_at)
            self.entered_at += duration
            if self._continue_at is not None:
                self._continue_at += duration
            self._paused_at = None

        if self.state == State.ERROR:
            self.resume(now)
            self._synchronize(visible, now)
            return []
        if self.state == State.DETECTING:
            was_resuming = self._resuming
            if not self._synchronize(visible, now):
                return []
            self._resuming = False
            # Fresh starts may perform the proven lobby P or bus Space path.
            # Resumes and terminal-screen recognition always observe one frame.
            if was_resuming or self.state not in {State.LOBBY, State.BATTLE_BUS}:
                return []

        # Expired evidence cannot authorize a late action or be refreshed by a
        # new screen. Pause adjustment must happen first on focus restoration.
        limit = self.timeouts.get(self.state.value)
        if limit is not None and now - self.entered_at >= limit:
            self.fail(f"Timeout in {self.state.value}; waiting for visual confirmation", now)
            return []

        # Returning is a separate trip, not matchmaking. Only a genuine lobby
        # ends it, including after stop/resume or an uncertain input exception.
        if self._return_sent:
            if not self._lobby_visible(visible):
                return []
            self._arrived_in_lobby(now)
        if self._awaiting_ready and not self._lobby_visible(visible):
            return []

        if self.state == State.SPECTATING:
            # A reboot returns to our active HUD. The same HUD can also be
            # visible while spectating, so require repeated active evidence
            # with no current observing/death/result/loading screen.
            active = bool(visible & {'in_match', 'falling', 'glider'})
            blockers = visible & {'spectating', 'own_dead', 'team_eliminated',
                                  'placement', 'match_summary', 'continue', 'skip',
                                  'replay', 'return_lobby', 'lobby', 'play',
                                  'loading', 'matchmaking', 'jump'}
            self._revive_streak = self._revive_streak + 1 if active and not blockers else 0
            if self._revive_streak >= 3:
                self._team_end = False
                self._continue_at = None
                self._jump_sent = True  # Revival is part of the same match.
                self._enter(State.IN_MATCH, now)
                return []

        # An alive teammate overrides terminal evidence even on result screens.
        alive = "teammate_alive" in visible
        result_context = self._team_end or bool(visible & {
            "team_eliminated", "placement", "match_summary", "continue", "skip", "replay", "return_lobby"})
        conflicting_context = visible & {
            "lobby", "play", "matchmaking", "loading", "jump", "in_match",
            "falling", "glider", "teammate_alive", "own_dead", "spectating"}
        if result_context and conflicting_context:
            self._team_end = False
            self._continue_at = None
            if (visible & {"own_dead", "spectating"}
                    or (alive and self.state in self.RESULT_STATES)):
                self._enter(State.SPECTATING, now)
            limit = self.timeouts.get(self.state.value)
            if limit is not None and now - self.entered_at >= limit:
                self.fail(f"Timeout in {self.state.value}; conflicting visual evidence", now)
            return []
        if alive:
            self._team_end = False
            self._continue_at = None
            if self.state in self.RESULT_STATES:
                self._enter(State.SPECTATING, now)
        elif self.state != State.RETURNING_TO_LOBBY and "team_eliminated" in visible and (
                "placement" in visible or "match_summary" in visible):
            self._team_end = True
            if self.state not in self.RESULT_STATES:
                self._enter(State.TEAM_ELIMINATED, now)

        if self._team_end and not alive and self.state != State.RETURNING_TO_LOBBY:
            if "continue" in visible and self._continue_at is None:
                self._continue_at = now
                self._enter(State.WAITING_FOR_RESULTS, now)
            # Continue auto-dismisses. Waiting never creates result proof.
            if "continue" not in visible and (
                    self._continue_at is None or now - self._continue_at >= 5):
                if "return_lobby" in visible and not self._return_sent:
                    self._enter(State.MATCH_SUMMARY, now)
                    self._return_sent = True
                    self._team_end = False
                    self._enter(State.RETURNING_TO_LOBBY, now)
                    return self._action("return_lobby")
                if "skip" in visible and not self._skip_sent:
                    self._skip_sent = True
                    self._enter(State.SKIP_XP, now)
                    return self._action("skip")
                if "match_summary" in visible:
                    self._enter(State.MATCH_SUMMARY, now)
        elif (self.state == State.IN_MATCH and not self._jump_sent
              and self._bus_visible(visible)):
            # The generic HUD is already visible on the spawn island. It is
            # evidence of an active match, never proof that Space was sent.
            self._count_round()
            self._enter(State.BATTLE_BUS, now)
            self._jump_sent = True
            self._enter(State.JUMPING, now)
            return self._action("jump")
        elif self.state == State.JUMPING:
            if "jump" not in visible and visible & {"in_match", "falling", "glider"}:
                self._enter(State.IN_MATCH, now)
        elif self.state in {State.LOBBY, State.MATCHMAKING, State.LOADING,
                            State.BATTLE_BUS}:
            # Conflicting death/result/match cues cannot trigger a bus input.
            bus = self._bus_visible(visible)
            next_state = None
            if bus:
                next_state = State.BATTLE_BUS
            elif "loading" in visible:
                next_state = State.LOADING
            elif "matchmaking" in visible:
                next_state = State.MATCHMAKING
            if next_state is not None:
                self._count_round()
                self._enter(next_state, now)
                if bus and not self._jump_sent:
                    self._jump_sent = True
                    self._enter(State.JUMPING, now)
                    return self._action("jump")
            elif self.state == State.LOBBY and visible & {"in_match", "falling", "glider"}:
                self._enter(State.IN_MATCH, now)
            elif self.state == State.LOBBY and {"lobby", "play"} <= visible:
                if mode_ok and not self._ready_sent and not alive:
                    self._ready_sent = True
                    self._awaiting_ready = False
                    # Stay in LOBBY until search/load/bus visibly confirms it.
                    self.entered_at = now
                    return self._action("ready")

        if not self._team_end and self.state in {
                State.LOBBY, State.JUMPING, State.IN_MATCH, State.SPECTATING}:
            if visible & {"own_dead", "spectating"}:
                self._enter(State.SPECTATING, now)

        limit = self.timeouts.get(self.state.value)
        if limit is not None and now - self.entered_at >= limit:
            self.fail(f"Timeout in {self.state.value}; waiting for visual confirmation", now)
        return []
