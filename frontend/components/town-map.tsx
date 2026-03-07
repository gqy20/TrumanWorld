"use client";

import { useEffect, useRef, useMemo } from "react";
import * as d3 from "d3";
import { motion } from "framer-motion";
import type { WorldSnapshot, AgentSummary } from "@/lib/api";

interface LocationNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  capacity: number;
  occupantCount: number;
  occupants: AgentSummary[];
}

interface LocationLink {
  source: string;
  target: string;
  distance: number;
}

interface TownMapProps {
  world: WorldSnapshot;
  agentNameMap: Record<string, string>;
  onLocationClick?: (locationId: string) => void;
  onAgentClick?: (agentId: string) => void;
}

// 地点类型对应的图标和颜色
const LOCATION_STYLES: Record<string, { icon: string; color: string; bgColor: string }> = {
  cafe: { icon: "☕", color: "#f59e0b", bgColor: "#fef3c7" },
  plaza: { icon: "🌳", color: "#0ea5e9", bgColor: "#e0f2fe" },
  park: { icon: "🌲", color: "#10b981", bgColor: "#d1fae5" },
  shop: { icon: "🏪", color: "#8b5cf6", bgColor: "#ede9fe" },
  home: { icon: "🏠", color: "#ec4899", bgColor: "#fce7f3" },
  default: { icon: "📍", color: "#6b7280", bgColor: "#f3f4f6" },
};

export function TownMap({ world, agentNameMap, onLocationClick, onAgentClick }: TownMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  
  // 准备数据
  const { nodes, links, bounds } = useMemo(() => {
    const locations = world.locations;
    
    // 计算边界
    const xExtent = d3.extent(locations, (d: { x: number }) => d.x) as [number, number];
    const yExtent = d3.extent(locations, (d: { y: number }) => d.y) as [number, number];
    const padding = 100;
    
    const bounds = {
      minX: (xExtent[0] || 0) - padding,
      maxX: (xExtent[1] || 0) + padding,
      minY: (yExtent[0] || 0) - padding,
      maxY: (yExtent[1] || 0) + padding,
    };
    
    // 创建节点（地点）
    const nodes: LocationNode[] = locations.map(loc => ({
      id: loc.id,
      name: loc.name,
      type: loc.location_type,
      x: loc.x,
      y: loc.y,
      capacity: loc.capacity,
      occupantCount: loc.occupants.length,
      occupants: loc.occupants,
    }));
    
    // 创建连接（基于距离，连接最近的3个地点）
    const links: LocationLink[] = [];
    for (let i = 0; i < nodes.length; i++) {
      const distances = nodes
        .filter((_, j) => j !== i)
        .map(n => ({
          id: n.id,
          distance: Math.sqrt(
            Math.pow(nodes[i].x - n.x, 2) + Math.pow(nodes[i].y - n.y, 2)
          ),
        }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 3);
      
      distances.forEach(d => {
        if (!links.find(l => 
          (l.source === nodes[i].id && l.target === d.id) ||
          (l.source === d.id && l.target === nodes[i].id)
        )) {
          links.push({
            source: nodes[i].id,
            target: d.id,
            distance: d.distance,
          });
        }
      });
    }
    
    return { nodes, links, bounds };
  }, [world]);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth;
    const height = 400;
    
    // 设置视图框
    const viewBoxWidth = bounds.maxX - bounds.minX;
    const viewBoxHeight = bounds.maxY - bounds.minY;
    svg.attr("viewBox", `${bounds.minX} ${bounds.minY} ${viewBoxWidth} ${viewBoxHeight}`);

    // 创建缩放行为
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // 主图形组
    const g = svg.append("g");

    // 定义渐变和滤镜
    const defs = svg.append("defs");
    
    // 发光滤镜
    const filter = defs.append("filter")
      .attr("id", "glow")
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");
    
    filter.append("feGaussianBlur")
      .attr("stdDeviation", "3")
      .attr("result", "coloredBlur");
    
    const feMerge = filter.append("feMerge");
    feMerge.append("feMergeNode").attr("in", "coloredBlur");
    feMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // 绘制连接线
    g.selectAll(".link")
      .data(links)
      .enter()
      .append("line")
      .attr("class", "link")
      .attr("x1", d => nodes.find(n => n.id === d.source)?.x || 0)
      .attr("y1", d => nodes.find(n => n.id === d.source)?.y || 0)
      .attr("x2", d => nodes.find(n => n.id === d.target)?.x || 0)
      .attr("y2", d => nodes.find(n => n.id === d.target)?.y || 0)
      .attr("stroke", "#cbd5e1")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "5,5")
      .attr("opacity", 0.6);

    // 绘制路径（行走路线）
    const moveEvents = world.recent_events.filter(e => e.event_type === "move");
    moveEvents.forEach((event, idx) => {
      const fromLoc = nodes.find(n => n.id === event.location_id);
      const toLoc = nodes.find(n => n.id === event.payload.to_location_id);
      
      if (fromLoc && toLoc) {
        // 绘制移动轨迹
        g.append("path")
          .attr("d", d3.line()([[fromLoc.x, fromLoc.y], [toLoc.x, toLoc.y]]))
          .attr("stroke", "#10b981")
          .attr("stroke-width", 3)
          .attr("fill", "none")
          .attr("opacity", 0)
          .attr("stroke-linecap", "round")
          .transition()
          .delay(idx * 100)
          .duration(1000)
          .attr("opacity", 0.4)
          .transition()
          .duration(2000)
          .attr("opacity", 0);
      }
    });

    // 绘制地点节点组
    const locationGroups = g.selectAll(".location")
      .data(nodes)
      .enter()
      .append("g")
      .attr("class", "location")
      .attr("transform", d => `translate(${d.x}, ${d.y})`)
      .style("cursor", "pointer")
      .on("click", (_, d) => onLocationClick?.(d.id));

    // 地点外圈（容量指示）
    locationGroups
      .append("circle")
      .attr("r", d => 30 + d.capacity * 3)
      .attr("fill", d => {
        const style = LOCATION_STYLES[d.type] || LOCATION_STYLES.default;
        return style.bgColor;
      })
      .attr("stroke", d => {
        const style = LOCATION_STYLES[d.type] || LOCATION_STYLES.default;
        return style.color;
      })
      .attr("stroke-width", 2)
      .attr("opacity", 0.3);

    // 地点主圆
    locationGroups
      .append("circle")
      .attr("r", 25)
      .attr("fill", "white")
      .attr("stroke", d => {
        const style = LOCATION_STYLES[d.type] || LOCATION_STYLES.default;
        return style.color;
      })
      .attr("stroke-width", 3)
      .style("filter", "url(#glow)");

    // 地点图标
    locationGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("font-size", "20")
      .text(d => {
        const style = LOCATION_STYLES[d.type] || LOCATION_STYLES.default;
        return style.icon;
      });

    // 地点名称
    locationGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 45)
      .attr("font-size", "12")
      .attr("font-weight", "600")
      .attr("fill", "#374151")
      .text(d => d.name);

    // 人数指示器
    locationGroups
      .filter(d => d.occupantCount > 0)
      .append("circle")
      .attr("cx", 18)
      .attr("cy", -18)
      .attr("r", 12)
      .attr("fill", "#ef4444")
      .attr("stroke", "white")
      .attr("stroke-width", 2);

    locationGroups
      .filter(d => d.occupantCount > 0)
      .append("text")
      .attr("x", 18)
      .attr("y", -18)
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("font-size", "10")
      .attr("font-weight", "bold")
      .attr("fill", "white")
      .text(d => d.occupantCount);

    // 绘制居民点 - 放置在地点圆圈外部，避免重叠
    nodes.forEach(node => {
      node.occupants.forEach((agent, idx) => {
        // 计算地点外圈半径
        const locationOuterRadius = 35 + node.capacity * 3 + 15; // 外圈 + 间距
        const angle = (idx / Math.max(node.occupants.length, 1)) * 2 * Math.PI - Math.PI / 2;
        const x = node.x + Math.cos(angle) * locationOuterRadius;
        const y = node.y + Math.sin(angle) * locationOuterRadius;

        const agentGroup = g.append("g")
          .attr("class", "agent")
          .attr("transform", `translate(${x}, ${y})`)
          .style("cursor", "pointer")
          .on("click", (e) => {
            e.stopPropagation();
            onAgentClick?.(agent.id);
          });

        // 居民圆圈
        agentGroup
          .append("circle")
          .attr("r", 14)
          .attr("fill", () => {
            const colors = ["#fbbf24", "#60a5fa", "#a78bfa", "#f472b6", "#34d399"];
            return colors[idx % colors.length];
          })
          .attr("stroke", "white")
          .attr("stroke-width", 3)
          .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.1))");

        // 居民名字首字母
        agentGroup
          .append("text")
          .attr("text-anchor", "middle")
          .attr("dy", "0.35em")
          .attr("font-size", "10")
          .attr("font-weight", "bold")
          .attr("fill", "white")
          .text(agent.name.charAt(0).toUpperCase());

        // 悬停提示（简单实现）
        agentGroup
          .append("title")
          .text(agent.name);
      });
    });

  }, [nodes, links, bounds, world.recent_events, onLocationClick, onAgentClick]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-3xl border border-slate-200 bg-white/80 p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs uppercase tracking-[0.22em] text-moss">小镇地图</div>
        <div className="flex gap-2 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            咖啡馆
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-sky-500" />
            广场
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            公园
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-violet-500" />
            商店
          </span>
        </div>
      </div>
      <svg
        ref={svgRef}
        className="w-full rounded-2xl bg-gradient-to-br from-slate-50 to-slate-100"
        style={{ height: 400 }}
      />
      <p className="mt-2 text-xs text-slate-400">
        点击地点查看详情，点击居民查看个人信息。绿色线条表示最近的移动路径。
      </p>
    </motion.div>
  );
}
