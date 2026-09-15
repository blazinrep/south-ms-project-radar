# TrackWatch Contractor Proof Case

_Last updated: 2026-09-14_

## Purpose

This is TrackWatch proof case #2.

GulfSouthDrags proves that TrackWatch can monitor racing information. Project Radar
tests whether the same idea works in a materially different industry: public
procurement and contractor opportunities.

The goal is not another generic page-diff tool. The goal is:

> **Watch the public opportunity sources a contractor depends on and interrupt the contractor only when something worth acting on changes.**

## Current adapter

`scripts/build_trackwatch_attention.py` consumes Project Radar's existing Mississippi
procurement change feed after the normal intelligence pipeline has built contractor
pursuit cards.

It classifies:

- new contractor-relevant opportunities
- deadlines that changed
- status / lifecycle changes
- pre-bid changes
- scope changes
- project value changes
- opportunities that are no longer open
- source-check failures

It filters:

- weak-fit opportunities that are not in the contractor's working lanes
- generic record changes that do not touch action-significant fields

Outputs:

- `data/intelligence/trackwatch_attention.json` — current attention queue
- `data/intelligence/trackwatch_metrics.json` — latest + cumulative proof metrics
- `state/trackwatch_attention_state.json` — dedupe state so reruns do not double-count

## Human-in-the-loop rule

TrackWatch does not bid, contact an owner, alter a contractor decision, or claim that
a source change is automatically true. It surfaces the change and the recommended
next check. The contractor or operator makes the decision.

## Commercial proof metrics

From day one, record:

- procurement change events scanned
- contractor-relevant changes surfaced
- low-value / weak-fit changes filtered
- source failures caught
- later: minutes of manual checking avoided
- later: opportunities pursued because TrackWatch surfaced them
- later: missed-change cost avoided

If TrackWatch works in both GulfSouthDrags and Project Radar while the industry
logic stays outside the core monitoring idea, that is evidence the product is
reusable.

## Next milestones

1. Let the adapter run against real Mississippi procurement changes.
2. Review false positives / false negatives.
3. Surface the attention queue directly in the Project Radar UI.
4. Add a notification channel for actionable changes.
5. Use the measured history as a TrackWatch commercial case study.
