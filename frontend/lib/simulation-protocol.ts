export const ACTION_MOVE = "move";
export const ACTION_TALK = "talk";
export const ACTION_WORK = "work";
export const ACTION_REST = "rest";
export const ACTION_LISTEN = "listen";
export const ACTION_CONVERSATION_STARTED = "conversation_started";
export const ACTION_CONVERSATION_JOINED = "conversation_joined";
export const EVENT_SPEECH = "speech";

export const EVENT_MOVE = ACTION_MOVE;
export const EVENT_TALK = ACTION_TALK;
export const EVENT_WORK = ACTION_WORK;
export const EVENT_REST = ACTION_REST;
export const EVENT_LISTEN = ACTION_LISTEN;
export const EVENT_CONVERSATION_STARTED = ACTION_CONVERSATION_STARTED;
export const EVENT_CONVERSATION_JOINED = ACTION_CONVERSATION_JOINED;
export const EVENT_PLAN = "plan";
export const EVENT_REFLECT = "reflect";

export const DIRECTOR_EVENT_PREFIX = "director_";
export const DIRECTOR_EVENT_INJECT = `${DIRECTOR_EVENT_PREFIX}inject`;
export const DIRECTOR_EVENT_BROADCAST = `${DIRECTOR_EVENT_PREFIX}broadcast`;
export const DIRECTOR_EVENT_ACTIVITY = `${DIRECTOR_EVENT_PREFIX}activity`;
export const DIRECTOR_EVENT_SHUTDOWN = `${DIRECTOR_EVENT_PREFIX}shutdown`;
export const DIRECTOR_EVENT_WEATHER_CHANGE = `${DIRECTOR_EVENT_PREFIX}weather_change`;
export const DIRECTOR_EVENT_POWER_OUTAGE = `${DIRECTOR_EVENT_PREFIX}power_outage`;

export const DIRECTOR_SCENE_SOFT_CHECK_IN = "soft_check_in";
export const DIRECTOR_SCENE_KEEP_NATURAL = "keep_scene_natural";

export type ActionType =
  | typeof ACTION_MOVE
  | typeof ACTION_TALK
  | typeof ACTION_WORK
  | typeof ACTION_REST
  | typeof ACTION_LISTEN
  | typeof ACTION_CONVERSATION_STARTED
  | typeof ACTION_CONVERSATION_JOINED
  | typeof EVENT_SPEECH
  | typeof EVENT_PLAN
  | typeof EVENT_REFLECT
  | typeof DIRECTOR_EVENT_INJECT
  | typeof DIRECTOR_EVENT_BROADCAST
  | typeof DIRECTOR_EVENT_ACTIVITY
  | typeof DIRECTOR_EVENT_SHUTDOWN
  | typeof DIRECTOR_EVENT_WEATHER_CHANGE
  | typeof DIRECTOR_EVENT_POWER_OUTAGE;

export type RejectedActionEventType =
  | `${typeof ACTION_MOVE}_rejected`
  | `${typeof ACTION_TALK}_rejected`
  | `${typeof ACTION_WORK}_rejected`
  | `${typeof ACTION_REST}_rejected`
  | `${typeof ACTION_LISTEN}_rejected`
  | `${typeof ACTION_CONVERSATION_STARTED}_rejected`
  | `${typeof ACTION_CONVERSATION_JOINED}_rejected`
  | `${typeof EVENT_SPEECH}_rejected`
  | `${typeof EVENT_PLAN}_rejected`
  | `${typeof EVENT_REFLECT}_rejected`
  | `${typeof DIRECTOR_EVENT_INJECT}_rejected`
  | `${typeof DIRECTOR_EVENT_BROADCAST}_rejected`
  | `${typeof DIRECTOR_EVENT_ACTIVITY}_rejected`
  | `${typeof DIRECTOR_EVENT_SHUTDOWN}_rejected`
  | `${typeof DIRECTOR_EVENT_WEATHER_CHANGE}_rejected`
  | `${typeof DIRECTOR_EVENT_POWER_OUTAGE}_rejected`;

export type EventType = ActionType | RejectedActionEventType;

export type DirectorSceneGoal =
  | typeof DIRECTOR_SCENE_SOFT_CHECK_IN
  | typeof DIRECTOR_SCENE_KEEP_NATURAL;

export function isDirectorEventType(eventType: string): boolean {
  return eventType.startsWith(DIRECTOR_EVENT_PREFIX);
}
