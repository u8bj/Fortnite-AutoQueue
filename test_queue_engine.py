"""Sequence tests use confirmed semantic cues, not live Fortnite recognition."""
import unittest

from queue_engine import Engine, State


class EngineTests(unittest.TestCase):
    def test_reboot_evidence_must_be_consecutive_and_focused(self):
        for interruption in ('blank', 'focus'):
            with self.subTest(interruption=interruption):
                self.engine.reset()
                self.enter_match()
                self.step('spectating', 5)
                self.step('in_match', 6)
                self.step('in_match', 7)
                self.engine.step(set() if interruption == 'blank' else {'in_match'}, 8,
                                 focused=interruption != 'focus')
                self.step('in_match', 9)
                self.step('in_match', 10)
                self.assertEqual(self.engine.state, State.SPECTATING)
                self.assertEqual(self.step('in_match', 11), [])
                self.assertEqual(self.engine.state, State.IN_MATCH)

    def test_reboot_returns_to_match_after_stable_active_evidence_without_input(self):
        self.enter_match()
        self.step('spectating teammate_alive', 5)
        self.assertEqual(self.engine.state, State.SPECTATING)
        for now in (6, 7):
            self.assertEqual(self.step('in_match', now), [])
            self.assertEqual(self.engine.state, State.SPECTATING)
        self.assertEqual(self.step('in_match', 8), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step('jump', 9), [])

    def test_spectator_does_not_resume_from_absence_or_conflicting_evidence(self):
        for evidence in ('', 'in_match spectating', 'in_match own_dead', 'in_match placement return_lobby'):
            with self.subTest(evidence=evidence):
                self.engine.reset()
                self.enter_match()
                self.step('spectating', 5)
                for now in range(6, 11):
                    self.assertEqual(self.step(evidence, now), [])
                self.assertEqual(self.engine.state, State.SPECTATING)

    def test_executed_space_immediately_enters_passive_wait_without_image(self):
        self.engine = Engine({'JUMPING': 2})
        self.assertEqual(self.engine.step({'jump'}, 0), ['jump'])
        acknowledge = getattr(self.engine, 'action_succeeded', None)
        self.assertIsNotNone(acknowledge, 'Successful input must end jump phase without a visual confirmation')
        acknowledge('jump', .2)
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.engine.step(set(), 30), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.engine.error, '')
        self.assertEqual(self.engine.step({'jump'}, 31), [])

    def setUp(self):
        self.engine = Engine()

    def step(self, cues, now, **kwargs):
        return self.engine.step(set(cues.split()), now, **kwargs)

    def enter_match(self):
        self.assertEqual(self.step("lobby play", 0), ["ready"])
        self.assertEqual(self.step("matchmaking", 1), [])
        self.assertEqual(self.step("loading", 2), [])
        self.assertEqual(self.step("jump", 3), ["jump"])
        self.assertEqual(self.step("falling", 4), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)

    def test_full_two_round_cycle(self):
        self.enter_match()
        self.assertEqual(self.engine.rounds, 1)
        self.step("own_dead spectating teammate_alive", 8)
        self.assertEqual(self.engine.state, State.SPECTATING)
        self.assertEqual(self.step("team_eliminated placement continue", 10), [])
        self.assertEqual(self.step("skip", 12), [])
        self.assertEqual(self.step("skip", 15), ["skip"])
        self.assertEqual(self.step("skip", 16), [])
        self.assertEqual(self.step("match_summary return_lobby", 17), ["return_lobby"])
        self.assertEqual(self.step("match_summary return_lobby", 18), [])
        self.assertEqual(self.step("loading", 20), [])
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("jump", 21), [])
        self.assertEqual(self.step("lobby play", 22), ["ready"])
        self.assertEqual(self.step("lobby play", 23), [])
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("loading", 24), [])
        self.assertEqual(self.engine.rounds, 2)
        self.assertEqual(self.step("jump", 25), ["jump"])

    def test_ready_needs_mode_and_both_lobby_cues(self):
        self.assertEqual(self.step("lobby", 0), [])
        self.assertEqual(self.step("lobby play", 1, mode_ok=False), [])
        self.assertEqual(self.step("lobby play", 2), ["ready"])
        self.assertEqual(self.step("lobby play", 3), [])
        self.assertEqual(self.engine.rounds, 0)

    def test_teammate_veto_revokes_previous_terminal_proof(self):
        self.enter_match()
        self.step("team_eliminated placement", 5)
        self.assertEqual(self.step("teammate_alive skip return_lobby match_summary placement", 6), [])
        self.assertEqual(self.step("skip return_lobby", 7), [])
        self.assertEqual(self.step("team_eliminated match_summary placement return_lobby", 8), ["return_lobby"])

    def test_single_terminal_cues_cannot_leave_match(self):
        self.enter_match()
        for now, cues in enumerate(("own_dead skip", "spectating return_lobby", "placement skip",
                                    "team_eliminated return_lobby", "match_summary return_lobby"), 5):
            self.assertEqual(self.step(cues, now), [])

    def test_direct_summary_and_direct_skip(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated match_summary return_lobby", 6), ["return_lobby"])
        self.engine.reset()
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement skip", 6), ["skip"])
        self.assertEqual(self.step("return_lobby", 7), ["return_lobby"])

    def test_focus_loss_does_not_send_or_expire_deadline(self):
        self.assertEqual(self.step("jump", 0, focused=False), [])
        self.assertEqual(self.step("jump", 1000), ["jump"])
        self.assertEqual(self.step("jump", 1001, focused=False), [])
        self.assertEqual(self.step("falling", 2000), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)

    def test_failed_jump_errors_without_retry(self):
        self.engine = Engine({"JUMPING": 2})
        self.assertEqual(self.step("jump", 0), ["jump"])
        self.assertEqual(self.step("jump in_match", 1), [])
        self.assertEqual(self.engine.state, State.JUMPING)
        self.assertEqual(self.step("jump", 3), [])
        self.assertEqual(self.engine.state, State.ERROR)
        self.assertIn("JUMPING", self.engine.error)
        self.assertEqual(self.step("jump", 4), [])

    def test_slow_loading_and_missing_bus_are_configurable(self):
        self.engine = Engine({"loading": 1000})
        self.step("loading", 0)
        self.step("", 999)
        self.assertEqual(self.engine.state, State.LOADING)
        self.step("", 1001)
        self.assertEqual(self.engine.state, State.ERROR)
        self.assertEqual(self.engine.rounds, 1)

    def test_restart_recovers_bus_or_match_without_mode_confirmation(self):
        self.assertEqual(self.step("jump", 0, mode_ok=False), ["jump"])
        self.assertEqual(self.engine.rounds, 1)
        self.engine.reset()
        self.assertEqual(self.step("jump spectating", 1), [])
        self.assertEqual(self.engine.state, State.SPECTATING)
        self.engine.reset()
        self.assertEqual(self.step("in_match", 1), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.engine.rounds, 0)

    def test_jump_is_once_and_requires_disappearing_prompt(self):
        self.enter_match()
        self.assertEqual(self.step("jump", 5), [])
        self.assertEqual(self.step("jump", 6), [])

    def test_conflicting_bus_and_loading_cues_cannot_jump(self):
        self.assertEqual(self.step("loading jump", 0), [])
        self.assertEqual(self.engine.state, State.LOADING)
        self.assertEqual(self.step("matchmaking jump", 1), [])
        self.assertEqual(self.step("jump", 2), ["jump"])

    def test_unfocused_result_does_not_issue_input(self):
        self.enter_match()
        self.step("team_eliminated placement", 5)
        self.assertEqual(self.step("return_lobby", 6, focused=False), [])
        self.assertEqual(self.step("return_lobby", 7), ["return_lobby"])

    def test_continue_overlay_blocks_overlapping_actions_after_five_seconds(self):
        self.enter_match()
        self.step("team_eliminated placement continue", 5)
        self.assertEqual(self.step("continue skip return_lobby", 11), [])
        self.assertEqual(self.step("continue skip return_lobby", 20), [])
        self.assertEqual(self.step("skip", 21), ["skip"])
        self.assertEqual(self.step("return_lobby", 22), ["return_lobby"])

    def test_alternating_result_cues_cannot_reset_timeout_forever(self):
        self.engine = Engine({"MATCH_SUMMARY": 10, "SKIP_XP": 10})
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement skip", 5), ["skip"])
        self.step("match_summary", 6)
        for now in range(7, 17):
            self.assertEqual(self.step("skip" if now % 2 else "match_summary", now), [])
        self.assertEqual(self.engine.state, State.ERROR)
        self.assertIn("MATCH_SUMMARY", self.engine.error)

    def test_personal_summary_and_placement_do_not_prove_team_elimination(self):
        self.enter_match()
        self.assertEqual(self.step("own_dead match_summary placement return_lobby", 5), [])
        self.assertEqual(self.step("match_summary placement return_lobby", 6), [])
        self.assertEqual(self.engine.state, State.SPECTATING)

    def test_terminal_proof_conflicting_with_live_context_cannot_send_input(self):
        for cue in ("lobby", "loading", "jump", "in_match", "falling", "glider", "teammate_alive"):
            with self.subTest(cue=cue):
                self.engine.reset()
                self.enter_match()
                self.assertEqual(self.step(f"team_eliminated placement skip return_lobby {cue}", 5), [])
                self.assertEqual(self.step("skip return_lobby", 6), [])

    def test_conflicting_live_context_revokes_retained_terminal_proof(self):
        self.enter_match()
        self.step("team_eliminated placement", 5)
        self.assertEqual(self.step("in_match return_lobby", 6), [])
        self.assertEqual(self.step("return_lobby", 7), [])

    def test_expired_terminal_proof_cannot_return_lobby(self):
        self.engine = Engine({"TEAM_ELIMINATED": 5})
        self.step("team_eliminated placement", 1)
        self.assertEqual(self.step("return_lobby", 100), [])
        self.assertEqual(self.engine.state, State.ERROR)
        self.assertIn("TEAM_ELIMINATED", self.engine.error)

    def test_overdue_lobby_cannot_ready_or_recover_bus(self):
        for cues in ("lobby play", "jump"):
            with self.subTest(cues=cues):
                self.engine.reset()
                self.step("lobby play", 0, mode_ok=False)
                self.assertEqual(self.step(cues, 121), [])
                self.assertEqual(self.engine.state, State.ERROR)
                self.assertEqual(self.engine.rounds, 0)

    def test_focus_restoration_does_not_hide_preexisting_expired_deadline(self):
        self.engine = Engine({"TEAM_ELIMINATED": 5})
        self.step("team_eliminated placement", 1)
        self.step("return_lobby", 10, focused=False)
        self.assertEqual(self.step("return_lobby", 100), [])
        self.assertEqual(self.engine.state, State.ERROR)

    def test_reset_and_explicit_failure(self):
        self.enter_match()
        self.engine.fail("input failed", 10)
        self.assertEqual(self.engine.error, "input failed")
        self.assertEqual(self.engine.entered_at, 10)
        self.assertEqual(self.step("lobby play", 11), [])
        self.engine.reset(20)
        self.assertEqual(self.engine.state, State.DETECTING)
        self.assertEqual(self.engine.rounds, 0)
        self.assertEqual(self.engine.error, "")
        self.assertEqual(self.engine.entered_at, 20)

    def test_enum_has_detection_and_thirteen_lifecycle_states(self):
        self.assertEqual(len(State), 14)

    def test_unknown_initial_screen_stays_passive_indefinitely(self):
        self.assertEqual(self.engine.state, State.DETECTING)
        for now in (0, 100, 100000):
            self.assertEqual(self.step("", now), [])
            self.assertEqual(self.engine.state, State.DETECTING)

    def test_timeout_recovers_to_spectating_without_input(self):
        self.engine = Engine({"IN_MATCH": 2})
        self.step("in_match", 0)
        self.step("", 3)
        self.assertEqual(self.engine.state, State.ERROR)
        self.assertEqual(self.step("own_dead spectating", 4), [])
        self.assertEqual(self.engine.state, State.SPECTATING)
        self.assertEqual(self.engine.error, "")

    def test_resume_observes_match_then_death_without_lobby_assumption(self):
        self.enter_match()
        self.engine.resume(10)
        self.assertEqual(self.engine.state, State.DETECTING)
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("in_match", 11), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.step("spectating", 12)
        self.assertEqual(self.engine.state, State.SPECTATING)

    def test_resume_after_space_cannot_repeat_space(self):
        self.assertEqual(self.step("jump", 0), ["jump"])
        self.engine.action_succeeded("jump", 1)
        self.engine.resume(2)
        self.assertEqual(self.step("jump", 3), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.step("jump", 4), [])

    def test_recovery_revokes_expired_proof_and_keeps_warning_while_unknown(self):
        self.engine = Engine({"TEAM_ELIMINATED": 2})
        self.step("team_eliminated placement", 0)
        self.step("", 3)
        self.assertEqual(self.step("return_lobby", 4), [])
        self.assertEqual(self.engine.state, State.DETECTING)
        self.assertTrue(self.engine.error)
        self.assertEqual(self.step("return_lobby", 100), [])
        self.assertEqual(self.step("team_eliminated placement return_lobby", 101), [])
        self.assertEqual(self.engine.state, State.TEAM_ELIMINATED)
        self.assertEqual(self.step("return_lobby", 102), ["return_lobby"])

    def test_resume_pending_ready_never_toggles_p_twice(self):
        self.assertEqual(self.step("lobby play", 0), ["ready"])
        self.engine.resume(1)
        self.assertEqual(self.step("lobby play", 2), [])
        self.assertEqual(self.step("lobby play", 3), [])

    def test_resume_from_match_to_real_lobby_can_start_new_round(self):
        self.enter_match()
        self.engine.resume(10)
        self.assertEqual(self.step("lobby play", 11), [])
        self.assertEqual(self.step("lobby play", 12), ["ready"])
        self.step("loading", 13)
        self.assertEqual(self.engine.rounds, 2)

    def test_cancelled_ready_retries_only_after_fresh_lobby_sync(self):
        self.assertEqual(self.step("lobby play", 0), ["ready"])
        self.engine.action_cancelled("ready", 1)
        self.assertEqual(self.engine.state, State.DETECTING)
        self.assertTrue(self.engine.error)
        self.assertEqual(self.step("lobby play", 2), [])
        self.assertEqual(self.step("lobby play", 3), ["ready"])
        self.assertEqual(self.step("lobby play", 4), [])

    def test_cancelled_jump_can_retry_but_successful_jump_never_retries(self):
        self.assertEqual(self.step("jump", 0), ["jump"])
        self.engine.action_cancelled("jump", 1)
        self.assertEqual(self.step("jump", 2), [])
        self.assertEqual(self.step("jump", 3), ["jump"])
        self.engine.action_succeeded("jump", 4)
        self.engine.resume(5)
        self.assertEqual(self.step("jump", 6), [])
        self.assertEqual(self.step("jump", 7), [])

    def test_exception_after_possible_jump_preserves_consumed_space(self):
        self.assertEqual(self.step("jump", 0), ["jump"])
        self.engine.fail("Input may have reached game", 1)
        self.assertEqual(self.step("jump", 2), [])
        self.assertEqual(self.step("jump", 3), [])

    def test_resume_preserves_consumed_skip_until_new_round(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement skip", 5), ["skip"])
        self.engine.resume(6)
        self.assertEqual(self.step("team_eliminated placement skip", 7), [])
        self.assertEqual(self.step("skip", 8), [])

    def test_recovery_prioritizes_positive_death_cue_over_result_ambiguity(self):
        self.engine.fail("temporary capture error", 1)
        self.assertEqual(self.step("own_dead teammate_alive team_eliminated placement return_lobby", 2), [])
        self.assertEqual(self.engine.state, State.SPECTATING)
        self.assertEqual(self.step("return_lobby", 3), [])

    def test_initial_bus_with_result_controls_is_not_unambiguous(self):
        for result in ("skip", "continue", "return_lobby"):
            with self.subTest(result=result):
                self.engine.reset()
                self.assertEqual(self.step(f"jump {result}", 0), [])
                self.assertEqual(self.engine.state, State.DETECTING)
                self.assertEqual(self.engine.rounds, 0)

    def test_return_resume_rejects_midmatch_cues_until_real_lobby(self):
        for cues in ("in_match", "spectating", "own_dead"):
            with self.subTest(cues=cues):
                self.engine.reset()
                self.enter_match()
                self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
                self.engine.resume(6)
                self.assertEqual(self.step(cues, 7), [])
                self.assertEqual(self.engine.rounds, 1)
                self.assertEqual(self.step("team_eliminated placement return_lobby", 8), [])
                self.assertEqual(self.step("lobby play", 9), [])
                self.assertEqual(self.step("lobby play", 10), ["ready"])

    def test_return_lobby_resume_stale_results_cannot_clear_consumed_actions(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.engine.resume(6)
        self.assertEqual(self.step("own_dead match_summary placement return_lobby", 7), [])
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("team_eliminated placement return_lobby", 8), [])
        self.assertEqual(self.step("return_lobby", 9), [])

    def test_spawn_island_hud_does_not_prevent_later_bus_jump(self):
        self.assertEqual(self.step("lobby play", 0), ["ready"])
        self.assertEqual(self.step("in_match", 1), [])
        self.assertEqual(self.engine.state, State.IN_MATCH)
        self.assertEqual(self.step("jump", 2), ["jump"])
        self.engine.action_succeeded("jump", 3)
        self.assertEqual(self.step("jump", 4), [])
        self.assertEqual(self.engine.rounds, 1)

    def test_resume_on_spawn_island_still_allows_first_bus_jump(self):
        self.assertEqual(self.step("lobby play", 0), ["ready"])
        self.step("in_match", 1)
        self.engine.resume(2)
        self.assertEqual(self.step("in_match", 3), [])
        self.assertEqual(self.step("jump", 4), ["jump"])
        self.engine.action_succeeded("jump", 5)
        self.engine.resume(6)
        self.assertEqual(self.step("in_match", 7), [])
        self.assertEqual(self.step("jump", 8), [])

    def test_spawn_island_bus_still_rejects_conflicting_result_and_death(self):
        for cue in ("own_dead", "spectating", "match_summary", "placement", "skip"):
            with self.subTest(cue=cue):
                self.engine.reset()
                self.step("in_match", 0)
                self.assertEqual(self.step(f"jump {cue}", 1), [])

    def test_current_death_or_spectating_revokes_retained_team_end_proof(self):
        for cue in ("spectating", "own_dead"):
            with self.subTest(cue=cue):
                self.engine.reset()
                self.enter_match()
                self.assertEqual(self.step("team_eliminated placement skip", 5), ["skip"])
                self.assertEqual(self.step(f"{cue} return_lobby", 6), [])
                self.assertEqual(self.engine.state, State.SPECTATING)
                self.assertEqual(self.step("return_lobby", 7), [])

    def test_explicit_terminal_proof_with_current_death_is_ambiguous(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement own_dead return_lobby", 5), [])
        self.assertEqual(self.engine.state, State.SPECTATING)
        self.assertEqual(self.step("return_lobby", 6), [])

    def test_return_result_screen_repeats_never_reclick(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.assertEqual(self.engine.state, State.RETURNING_TO_LOBBY)
        for now in range(6, 11):
            self.assertEqual(self.step("team_eliminated placement return_lobby", now), [])

    def test_replay_button_is_readonly_and_never_an_action(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement replay", 5), [])
        self.assertEqual(self.step("replay", 6), [])
        self.assertEqual(self.step("return_lobby", 7), ["return_lobby"])

    def test_return_lobby_is_gated_by_mode_and_real_lobby(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.assertEqual(self.step("lobby", 6), [])
        self.assertEqual(self.step("lobby play", 7, mode_ok=False), [])
        self.assertEqual(self.engine.state, State.LOBBY)
        self.assertEqual(self.step("lobby play", 8), ["ready"])
        self.assertEqual(self.step("lobby play", 9), [])

    def test_return_timeout_and_resume_still_wait_for_real_lobby(self):
        self.engine = Engine({"RETURNING_TO_LOBBY": 2})
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.assertEqual(self.step("loading", 8), [])
        self.assertEqual(self.engine.state, State.ERROR)
        for now, cues in ((9, "loading"), (10, "jump"), (11, "team_eliminated placement return_lobby")):
            self.assertEqual(self.step(cues, now), [])
            self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("lobby play", 12), [])
        self.assertEqual(self.step("lobby play", 13), ["ready"])

    def test_known_unsent_return_can_retry_after_fresh_terminal_proof(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.engine.action_cancelled("return_lobby", 6)
        self.assertEqual(self.step("return_lobby", 7), [])
        self.assertEqual(self.step("team_eliminated placement return_lobby", 8), [])
        self.assertEqual(self.step("return_lobby", 9), ["return_lobby"])

    def test_post_return_loading_and_bus_cannot_start_round_before_new_p(self):
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement return_lobby", 5), ["return_lobby"])
        self.assertEqual(self.step("lobby play", 6, mode_ok=False), [])
        self.assertEqual(self.step("loading", 7, mode_ok=False), [])
        self.assertEqual(self.step("jump", 8, mode_ok=False), [])
        self.assertEqual(self.engine.rounds, 1)
        self.engine.resume(9)
        self.assertEqual(self.step("jump", 10), [])
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("lobby play", 11), [])
        self.assertEqual(self.step("lobby play", 12), ["ready"])
        self.assertEqual(self.step("loading", 13), [])
        self.assertEqual(self.engine.rounds, 2)

    def test_legacy_replay_timeout_key_is_tolerated_without_replay_action(self):
        self.engine = Engine({"REPLAY": 15})
        self.enter_match()
        self.assertEqual(self.step("team_eliminated placement replay", 5), [])
        self.assertEqual(self.step("return_lobby", 6), ["return_lobby"])

    def test_cancelled_post_return_p_cannot_accept_search_before_retry(self):
        self.enter_match()
        self.step("team_eliminated placement return_lobby", 5)
        self.assertEqual(self.step("lobby play", 6), ["ready"])
        self.engine.action_cancelled("ready", 7)
        self.assertEqual(self.step("loading", 8), [])
        self.assertEqual(self.step("jump", 9), [])
        self.assertEqual(self.engine.rounds, 1)
        self.assertEqual(self.step("lobby play", 10), [])
        self.assertEqual(self.step("lobby play", 11), ["ready"])


if __name__ == "__main__":
    unittest.main()
