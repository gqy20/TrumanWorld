"use client";

import { useEffect, useRef, useState } from "react";

import type { WorldEvent } from "@/lib/types";

export type SpeechBubble = {
  message: string;
  key: number;
};

export type SpeechBubbleMap = Record<string, SpeechBubble>;

const MAX_BUBBLES = 4;
const BUBBLE_TTL_MS = 6000;

export function useSpeechBubbles(recentEvents: WorldEvent[]): SpeechBubbleMap {
  const [speechBubbles, setSpeechBubbles] = useState<SpeechBubbleMap>({});
  const bubbleTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const prevEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const speechEvents = recentEvents.filter(
      (event) =>
        (event.event_type === "speech" || event.event_type === "talk") && event.actor_agent_id,
    );

    const newBubbles: SpeechBubbleMap = {};
    for (const event of speechEvents) {
      const agentId = event.actor_agent_id;
      const message = typeof event.payload.message === "string" ? event.payload.message : null;
      if (!agentId || !message || prevEventIdsRef.current.has(event.id)) {
        continue;
      }
      newBubbles[agentId] = { message, key: Date.now() };
    }

    prevEventIdsRef.current = new Set(recentEvents.map((event) => event.id));

    if (Object.keys(newBubbles).length === 0) {
      return;
    }

    setSpeechBubbles((prev) => {
      const next = { ...prev };
      for (const [agentId, bubble] of Object.entries(newBubbles)) {
        next[agentId] = bubble;
        if (bubbleTimersRef.current[agentId]) {
          clearTimeout(bubbleTimersRef.current[agentId]);
        }
        bubbleTimersRef.current[agentId] = setTimeout(() => {
          setSpeechBubbles((current) => {
            const updated = { ...current };
            delete updated[agentId];
            return updated;
          });
          delete bubbleTimersRef.current[agentId];
        }, BUBBLE_TTL_MS);
      }

      const entries = Object.entries(next);
      if (entries.length > MAX_BUBBLES) {
        entries.sort((left, right) => left[1].key - right[1].key);
        const toRemove = entries.slice(0, entries.length - MAX_BUBBLES);
        for (const [agentId] of toRemove) {
          delete next[agentId];
          if (bubbleTimersRef.current[agentId]) {
            clearTimeout(bubbleTimersRef.current[agentId]);
            delete bubbleTimersRef.current[agentId];
          }
        }
      }
      return next;
    });
  }, [recentEvents]);

  useEffect(() => {
    return () => {
      for (const timer of Object.values(bubbleTimersRef.current)) {
        clearTimeout(timer);
      }
      bubbleTimersRef.current = {};
    };
  }, []);

  return speechBubbles;
}
