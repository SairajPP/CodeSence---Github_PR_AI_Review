"use client";

import { useEffect, useState } from "react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from "recharts";
import { 
  ShieldAlert, 
  Zap, 
  FileCode2, 
  Paintbrush, 
  CheckCircle2, 
  AlertTriangle, 
  Info,
  GitPullRequest
} from "lucide-react";

// Types
type Finding = {
  repo: string;
  title: string;
  explanation: string;
  agent: string;
  severity: "critical" | "warning" | "info";
};

type DashboardData = {
  findings: Finding[];
  error?: string;
};

// Colors for charts
const COLORS = {
  critical: "#ef4444", // red-500
  warning: "#eab308",  // yellow-500
  info: "#3b82f6",     // blue-500
};

const AGENT_COLORS = {
  security: "#ef4444",
  performance: "#f97316",
  logic: "#8b5cf6",
  style: "#10b981"
};

export default function Dashboard() {
  const [data, setData] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRepo, setSelectedRepo] = useState<string>("All Repositories");

  useEffect(() => {
    fetch("http://localhost:8000/api/dashboard/findings")
      .then((res) => res.json())
      .then((json: DashboardData) => {
        if (json.findings) {
          setData(json.findings);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch dashboard data", err);
        setLoading(false);
      });
  }, []);

  const repos = ["All Repositories", ...Array.from(new Set(data.map((f) => f.repo)))];
  
  const filteredData = selectedRepo === "All Repositories" 
    ? data 
    : data.filter(f => f.repo === selectedRepo);

  // Stats calculation
  const totalIssues = filteredData.length;
  const criticalCount = filteredData.filter(f => f.severity === "critical").length;
  const warningCount = filteredData.filter(f => f.severity === "warning").length;
  const infoCount = filteredData.filter(f => f.severity === "info").length;

  // Chart Data preparation
  const severityData = [
    { name: "Critical", value: criticalCount, fill: COLORS.critical },
    { name: "Warning", value: warningCount, fill: COLORS.warning },
    { name: "Info", value: infoCount, fill: COLORS.info },
  ];

  const agentStats = filteredData.reduce((acc, curr) => {
    acc[curr.agent] = (acc[curr.agent] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const agentData = Object.entries(agentStats).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    fill: AGENT_COLORS[name as keyof typeof AGENT_COLORS] || "#cbd5e1"
  }));

  const getAgentIcon = (agent: string) => {
    switch(agent) {
      case "security": return <ShieldAlert className="w-4 h-4 text-red-500" />;
      case "performance": return <Zap className="w-4 h-4 text-orange-500" />;
      case "logic": return <FileCode2 className="w-4 h-4 text-purple-500" />;
      case "style": return <Paintbrush className="w-4 h-4 text-emerald-500" />;
      default: return <Info className="w-4 h-4 text-gray-500" />;
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch(severity) {
      case "critical": return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case "warning": return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case "info": return <Info className="w-4 h-4 text-blue-500" />;
      default: return null;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
        <div className="text-emerald-400 animate-pulse text-xl font-semibold tracking-wider">INITIALIZING CODESENSE AI...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-200 font-sans p-6 md:p-10">
      
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 pb-6 border-b border-neutral-800">
        <div className="flex items-center gap-3 mb-4 md:mb-0">
          <div className="bg-emerald-500/10 p-3 rounded-xl border border-emerald-500/20">
            <GitPullRequest className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">CodeSense Dashboard</h1>
            <p className="text-neutral-400 text-sm">AI-Powered Pull Request Analytics</p>
          </div>
        </div>
        
        <select 
          className="bg-neutral-900 border border-neutral-800 text-white rounded-lg px-4 py-2 outline-none focus:border-emerald-500 transition-colors"
          value={selectedRepo}
          onChange={(e) => setSelectedRepo(e.target.value)}
        >
          {repos.map(repo => (
            <option key={repo} value={repo}>{repo}</option>
          ))}
        </select>
      </header>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm hover:border-emerald-500/50 transition-colors">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-neutral-400 font-medium">Total Issues Found</h3>
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          </div>
          <p className="text-4xl font-bold text-white">{totalIssues}</p>
        </div>
        
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm hover:border-red-500/50 transition-colors">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-neutral-400 font-medium">Critical</h3>
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <p className="text-4xl font-bold text-white">{criticalCount}</p>
        </div>

        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm hover:border-yellow-500/50 transition-colors">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-neutral-400 font-medium">Warnings</h3>
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
          </div>
          <p className="text-4xl font-bold text-white">{warningCount}</p>
        </div>

        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6 backdrop-blur-sm hover:border-blue-500/50 transition-colors">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-neutral-400 font-medium">Info</h3>
            <Info className="w-5 h-5 text-blue-500" />
          </div>
          <p className="text-4xl font-bold text-white">{infoCount}</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        {/* Severity Chart */}
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-6">Issues by Severity</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={severityData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                <XAxis dataKey="name" stroke="#525252" tick={{ fill: '#a3a3a3' }} />
                <YAxis stroke="#525252" tick={{ fill: '#a3a3a3' }} />
                <Tooltip 
                  cursor={{ fill: '#262626', opacity: 0.4 }}
                  contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040', borderRadius: '8px' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {severityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Agent Distribution */}
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-6">Agent Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={agentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {agentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040', borderRadius: '8px' }}
                  itemStyle={{ color: '#e5e5e5' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 mt-2">
            {agentData.map((entry, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-neutral-400">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.fill }} />
                {entry.name}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Findings List */}
      <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl overflow-hidden">
        <div className="p-6 border-b border-neutral-800">
          <h3 className="text-lg font-semibold text-white">Recent AI Findings</h3>
        </div>
        
        {filteredData.length === 0 ? (
          <div className="p-10 text-center text-neutral-500">
            No findings recorded yet. Open a Pull Request to start analyzing!
          </div>
        ) : (
          <div className="divide-y divide-neutral-800 max-h-[600px] overflow-y-auto">
            {filteredData.map((finding, idx) => (
              <div key={idx} className="p-6 hover:bg-neutral-800/30 transition-colors">
                <div className="flex items-start gap-4">
                  <div className="mt-1">
                    {getSeverityIcon(finding.severity)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-white font-medium truncate">{finding.title}</h4>
                      <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-neutral-800 text-neutral-300 border border-neutral-700">
                        {getAgentIcon(finding.agent)}
                        <span className="capitalize">{finding.agent}</span>
                      </span>
                    </div>
                    <p className="text-sm text-neutral-400 mb-2 leading-relaxed">
                      {finding.explanation}
                    </p>
                    <div className="flex items-center gap-4 text-xs font-mono text-neutral-500">
                      <span>repo: {finding.repo}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
