import { inferAgentStatus, type AgentStatus } from "@/lib/agent-utils";
import { EVENT_MOVE, EVENT_SPEECH, EVENT_TALK } from "@/lib/simulation-protocol";
import type { AgentSummary, WorldSnapshot } from "@/lib/types";
import {
  buildWorldNameMaps,
  calculateLocationHeat,
  getTimeOfDay,
  getTimeOfDayStyle,
  type TimeOfDay,
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
  movementId?: string;
};

export type SceneMoveTrail = {
  id: string;
  actorId?: string;
  actorName: string;
  fromLocationId: string;
  toLocationId: string;
  recencyIndex: number;
  initialProgress?: number;
  isActive?: boolean;
  routeNodeIds?: string[];
};

export type SceneNavigation = {
  nodes: Array<{ id: string; x: number; z: number }>;
  edges: Array<{ fromNodeId: string; toNodeId: string; distance: number }>;
  locationEntrances: Record<string, string>;
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
  isRunning: boolean;
  locations: SceneLocation[];
  agents: SceneAgent[];
  activeMovements: SceneMoveTrail[];
  moveTrails: SceneMoveTrail[];
  bubbles: SceneBubble[];
  navigation?: SceneNavigation;
  ambience: {
    label: string;
    overlayColor: string;
    isDark: boolean;
    hour?: number;
    timeOfDay?: TimeOfDay;
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
  const worldAgents = resolveWorldAgents(world);
  const navigation = centerNavigation(world.navigation);
  const agentsByAnchorLocation = new Map<string, AgentSummary[]>();

  for (const agent of worldAgents) {
    const anchorLocationId = agent.movement?.from_location_id ?? agent.current_location_id;
    if (!anchorLocationId || !locationIds.has(anchorLocationId)) continue;
    const locationAgents = agentsByAnchorLocation.get(anchorLocationId) ?? [];
    locationAgents.push(agent);
    agentsByAnchorLocation.set(anchorLocationId, locationAgents);
  }

  for (const [locationId, locationAgents] of agentsByAnchorLocation) {
    locationAgents
      .sort((left, right) => left.id.localeCompare(right.id))
      .forEach((agent, index) => {
        const status = agent.movement
          ? "moving"
          : inferAgentStatus(agent.id, world.recent_events);
        const agentVisualConfig = world.ui_config?.stage?.agents?.statuses?.[
          status
        ];
        agents.push({
          id: agent.id,
          name: agent.name,
          occupation: agent.occupation,
          locationId,
          status,
          slotIndex: index,
          movementId: agent.movement?.id,
          visual: {
            visualPreset: agentVisualConfig?.visual_preset ?? undefined,
            marker: agentVisualConfig?.marker ?? undefined,
          },
        });
      });
  }

  const activeMovements = worldAgents.flatMap((agent, index) => {
    const movement = agent.movement;
    if (
      !movement ||
      !locationIds.has(movement.from_location_id) ||
      !locationIds.has(movement.to_location_id)
    ) {
      return [];
    }
    const durationTicks = Math.max(1, movement.arrival_tick - movement.started_tick);
    const currentTick = world.run.current_tick ?? movement.started_tick;
    return [
      {
        id: movement.id,
        actorId: agent.id,
        actorName: agent.name,
        fromLocationId: movement.from_location_id,
        toLocationId: movement.to_location_id,
        recencyIndex: index,
        initialProgress: Math.min(
          1,
          Math.max(0, (currentTick - movement.started_tick) / durationTicks),
        ),
        isActive: true,
        routeNodeIds: movement.route_node_ids,
      },
    ];
  });
  const activeMovementIds = new Set(activeMovements.map((movement) => movement.id));

  return {
    runId: world.run.id,
    isRunning: world.run.status === "running",
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
    activeMovements,
    moveTrails: world.recent_events
      .filter((event) => event.event_type === EVENT_MOVE)
      .slice(0, 4)
      .map((event, index) => {
        const fromLocationId = String(event.payload.from_location_id ?? "");
        const toLocationId = String(event.payload.to_location_id ?? event.location_id ?? "");
        return {
          id: String(event.payload.movement_id ?? event.id),
          actorId: event.actor_agent_id,
          actorName:
            agentNameMap[event.actor_agent_id ?? ""] ?? event.actor_name ?? event.actor_agent_id ?? "某人",
          fromLocationId,
          toLocationId,
          recencyIndex: index,
          routeNodeIds: Array.isArray(event.payload.route_node_ids)
            ? event.payload.route_node_ids.filter(
                (nodeId): nodeId is string => typeof nodeId === "string",
              )
            : undefined,
        };
      })
      .filter(
        (trail) => locationIds.has(trail.fromLocationId) && locationIds.has(trail.toLocationId)
      )
      .filter((trail) => !activeMovementIds.has(trail.id)),
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
    navigation,
    ambience: {
      label: timeStyle.label,
      overlayColor: timeStyle.overlayColor,
      isDark: timeStyle.isDark,
      hour: world.world_clock?.hour ?? 12,
      timeOfDay,
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

function centerNavigation(navigation: WorldSnapshot["navigation"]): SceneNavigation {
  if (!navigation || navigation.nodes.length === 0) {
    return { nodes: [], edges: [], locationEntrances: {} };
  }
  const minX = Math.min(...navigation.nodes.map((node) => node.x));
  const maxX = Math.max(...navigation.nodes.map((node) => node.x));
  const minY = Math.min(...navigation.nodes.map((node) => node.y));
  const maxY = Math.max(...navigation.nodes.map((node) => node.y));
  const offsetX = (minX + maxX) / 2;
  const offsetY = (minY + maxY) / 2;
  return {
    nodes: navigation.nodes.map((node) => ({
      id: node.id,
      x: node.x - offsetX,
      z: node.y - offsetY,
    })),
    edges: navigation.edges.map((edge) => ({
      fromNodeId: edge.from_node_id,
      toNodeId: edge.to_node_id,
      distance: edge.distance,
    })),
    locationEntrances: navigation.location_entrances,
  };
}

function resolveWorldAgents(world: WorldSnapshot): AgentSummary[] {
  if (world.agents) return world.agents;
  const agents = world.locations.flatMap((location) => location.occupants);
  return agents.filter(
    (agent, index) => agents.findIndex((candidate) => candidate.id === agent.id) === index,
  );
}
