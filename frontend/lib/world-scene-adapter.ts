import { inferAgentStatus, type AgentStatus } from "@/lib/agent-utils";
import { EVENT_MOVE, EVENT_SPEECH, EVENT_TALK } from "@/lib/simulation-protocol";
import type { WorldSnapshot } from "@/lib/types";
import {
  buildWorldNameMaps,
  calculateLocationHeat,
  getTimeOfDay,
  getTimeOfDayStyle,
} from "@/lib/world-utils";

export type SceneLocationVisual = {
  visualPreset?: string;
  glyph?: string;
};

export type SceneAgentVisual = {
  visualPreset?: string;
  marker?: string;
};

export type SceneStagePalette = {
  backgroundColor?: string;
  headerColor?: string;
  headerAlpha?: number;
  vignetteColor?: string;
  vignetteAlpha?: number;
  labelColor?: string;
};

export type SceneLocation = {
  id: string;
  name: string;
  locationType: string;
  visual: SceneLocationVisual;
  x: number;
  y: number;
  capacity: number;
  occupantCount: number;
  heat: number;
};

export type SceneAgent = {
  id: string;
  name: string;
  occupation?: string;
  locationId: string;
  status: AgentStatus;
  slotIndex: number;
  visual?: SceneAgentVisual;
};

export type SceneMoveTrail = {
  id: string;
  actorId?: string;
  actorName: string;
  fromLocationId: string;
  toLocationId: string;
  recencyIndex: number;
};

export type SceneBubble = {
  id: string;
  text: string;
  speakerAgentId?: string;
  speakerName: string;
  locationId: string;
  recencyIndex: number;
};

export type SceneWorld = {
  runId: string;
  locations: SceneLocation[];
  agents: SceneAgent[];
  moveTrails: SceneMoveTrail[];
  bubbles: SceneBubble[];
  ambience: {
    label: string;
    overlayColor: string;
    isDark: boolean;
  };
  stage: {
    theme?: string;
    groundPreset?: string;
    palette?: SceneStagePalette;
  };
};

export function buildSceneWorld(world: WorldSnapshot): SceneWorld {
  const agents: SceneAgent[] = [];
  const { agentNameMap } = buildWorldNameMaps(world);
  const locationIds = new Set(world.locations.map((location) => location.id));
  const timeOfDay = getTimeOfDay(world.world_clock?.hour ?? 12);
  const timeStyle = getTimeOfDayStyle(timeOfDay);

  for (const location of world.locations) {
    location.occupants
      .slice()
      .sort((left, right) => left.id.localeCompare(right.id))
      .forEach((agent, index) => {
        const agentVisualConfig = world.ui_config?.stage?.agents?.statuses?.[
          inferAgentStatus(agent.id, world.recent_events)
        ];
        agents.push({
          id: agent.id,
          name: agent.name,
          occupation: agent.occupation,
          locationId: location.id,
          status: inferAgentStatus(agent.id, world.recent_events),
          slotIndex: index,
          visual: {
            visualPreset: agentVisualConfig?.visual_preset ?? undefined,
            marker: agentVisualConfig?.marker ?? undefined,
          },
        });
      });
  }

  return {
    runId: world.run.id,
    locations: world.locations.map((location) => {
      const visualConfig = world.ui_config?.stage?.location_types?.[location.location_type];
      return {
        id: location.id,
        name: location.name,
        locationType: location.location_type,
        visual: {
          visualPreset: visualConfig?.visual_preset ?? location.location_type,
          glyph: visualConfig?.glyph ?? undefined,
        },
        x: location.x,
        y: location.y,
        capacity: location.capacity,
        occupantCount: location.occupants.length,
        heat: calculateLocationHeat(location.id, world.recent_events),
      };
    }),
    agents,
    moveTrails: world.recent_events
      .filter((event) => event.event_type === EVENT_MOVE)
      .slice(0, 4)
      .map((event, index) => {
        const fromLocationId = String(event.payload.from_location_id ?? "");
        const toLocationId = String(event.payload.to_location_id ?? event.location_id ?? "");
        return {
          id: event.id,
          actorId: event.actor_agent_id,
          actorName:
            agentNameMap[event.actor_agent_id ?? ""] ?? event.actor_name ?? event.actor_agent_id ?? "某人",
          fromLocationId,
          toLocationId,
          recencyIndex: index,
        };
      })
      .filter(
        (trail) => locationIds.has(trail.fromLocationId) && locationIds.has(trail.toLocationId)
      ),
    bubbles: world.recent_events
      .filter((event) => event.event_type === EVENT_SPEECH || event.event_type === EVENT_TALK)
      .slice(0, 2)
      .map((event, index) => {
        const text = String(event.payload.message ?? "").trim();
        const locationId = String(event.location_id ?? "");
        return {
          id: event.id,
          text: text.length > 22 ? `${text.slice(0, 22)}…` : text,
          speakerAgentId: event.actor_agent_id,
          speakerName:
            agentNameMap[event.actor_agent_id ?? ""] ?? event.actor_name ?? event.actor_agent_id ?? "某人",
          locationId,
          recencyIndex: index,
        };
      })
      .filter((bubble) => bubble.text.length > 0 && locationIds.has(bubble.locationId)),
    ambience: {
      label: timeStyle.label,
      overlayColor: timeStyle.overlayColor,
      isDark: timeStyle.isDark,
    },
    stage: {
      theme: world.ui_config?.stage?.theme ?? undefined,
      groundPreset: world.ui_config?.stage?.ground_preset ?? undefined,
      palette: {
        backgroundColor: world.ui_config?.stage?.palette?.background_color ?? undefined,
        headerColor: world.ui_config?.stage?.palette?.header_color ?? undefined,
        headerAlpha: world.ui_config?.stage?.palette?.header_alpha ?? undefined,
        vignetteColor: world.ui_config?.stage?.palette?.vignette_color ?? undefined,
        vignetteAlpha: world.ui_config?.stage?.palette?.vignette_alpha ?? undefined,
        labelColor: world.ui_config?.stage?.palette?.label_color ?? undefined,
      },
    },
  };
}
