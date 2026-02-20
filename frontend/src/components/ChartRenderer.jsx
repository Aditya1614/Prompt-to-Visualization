import {
    LineChart, Line,
    BarChart, Bar,
    PieChart, Pie, Cell,
    ScatterChart, Scatter,
    AreaChart, Area,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

/**
 * Color palette for charts — vibrant, modern colors.
 */
const DEFAULT_COLORS = [
    "#6366f1", "#8b5cf6", "#a78bfa", "#c084fc",
    "#e879f9", "#f472b6", "#fb7185", "#f97316",
    "#facc15", "#34d399", "#22d3ee", "#60a5fa",
];

/**
 * Dynamic chart renderer — maps chart_type to Recharts component.
 */
export default function ChartRenderer({ chartType, chartConfig }) {
    if (!chartConfig || !chartConfig.data || chartConfig.data.length === 0) {
        return (
            <div className="chart-empty">
                <p>No data to display</p>
            </div>
        );
    }

    const { x_field, y_field, data, title, x_label, y_label, colors } = chartConfig;
    const palette = colors && colors.length > 0 ? colors : DEFAULT_COLORS;

    // Normalize y_field to always be an array
    const yFields = Array.isArray(y_field) ? y_field : [y_field];

    const commonProps = {
        data,
        margin: { top: 20, right: 30, left: 20, bottom: 20 },
    };

    const renderChart = () => {
        switch (chartType) {
            case "line":
                return (
                    <LineChart {...commonProps}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                        <XAxis
                            dataKey={x_field}
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={x_label ? { value: x_label, position: "insideBottom", offset: -10, fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <YAxis
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={y_label ? { value: y_label, angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <Tooltip
                            contentStyle={{
                                background: "rgba(15, 15, 35, 0.95)",
                                border: "1px solid rgba(99, 102, 241, 0.3)",
                                borderRadius: "12px",
                                color: "#e2e8f0",
                                backdropFilter: "blur(10px)",
                            }}
                        />
                        <Legend wrapperStyle={{ color: "rgba(255,255,255,0.7)" }} />
                        {yFields.map((field, i) => (
                            <Line
                                key={field}
                                type="monotone"
                                dataKey={field}
                                stroke={palette[i % palette.length]}
                                strokeWidth={2.5}
                                dot={{ r: 4, fill: palette[i % palette.length] }}
                                activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }}
                            />
                        ))}
                    </LineChart>
                );

            case "bar":
                return (
                    <BarChart {...commonProps}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                        <XAxis
                            dataKey={x_field}
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={x_label ? { value: x_label, position: "insideBottom", offset: -10, fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <YAxis
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={y_label ? { value: y_label, angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <Tooltip
                            contentStyle={{
                                background: "rgba(15, 15, 35, 0.95)",
                                border: "1px solid rgba(99, 102, 241, 0.3)",
                                borderRadius: "12px",
                                color: "#e2e8f0",
                                backdropFilter: "blur(10px)",
                            }}
                        />
                        <Legend wrapperStyle={{ color: "rgba(255,255,255,0.7)" }} />
                        {yFields.map((field, i) => (
                            <Bar
                                key={field}
                                dataKey={field}
                                fill={palette[i % palette.length]}
                                radius={[6, 6, 0, 0]}
                                maxBarSize={60}
                            />
                        ))}
                    </BarChart>
                );

            case "pie":
                return (
                    <PieChart>
                        <Pie
                            data={data}
                            dataKey={yFields[0]}
                            nameKey={x_field}
                            cx="50%"
                            cy="50%"
                            outerRadius="75%"
                            innerRadius="40%"
                            paddingAngle={3}
                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                            labelLine={{ stroke: "rgba(255,255,255,0.3)" }}
                        >
                            {data.map((_, i) => (
                                <Cell key={i} fill={palette[i % palette.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{
                                background: "rgba(15, 15, 35, 0.95)",
                                border: "1px solid rgba(99, 102, 241, 0.3)",
                                borderRadius: "12px",
                                color: "#e2e8f0",
                            }}
                        />
                        <Legend wrapperStyle={{ color: "rgba(255,255,255,0.7)" }} />
                    </PieChart>
                );

            case "scatter":
                return (
                    <ScatterChart {...commonProps}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                        <XAxis
                            dataKey={x_field}
                            type="number"
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={x_label ? { value: x_label, position: "insideBottom", offset: -10, fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <YAxis
                            dataKey={yFields[0]}
                            type="number"
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={y_label ? { value: y_label, angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <Tooltip
                            contentStyle={{
                                background: "rgba(15, 15, 35, 0.95)",
                                border: "1px solid rgba(99, 102, 241, 0.3)",
                                borderRadius: "12px",
                                color: "#e2e8f0",
                            }}
                        />
                        <Scatter
                            data={data}
                            fill={palette[0]}
                            shape="circle"
                        />
                    </ScatterChart>
                );

            case "area":
                return (
                    <AreaChart {...commonProps}>
                        <defs>
                            {yFields.map((field, i) => (
                                <linearGradient key={field} id={`gradient-${i}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor={palette[i % palette.length]} stopOpacity={0.4} />
                                    <stop offset="95%" stopColor={palette[i % palette.length]} stopOpacity={0.05} />
                                </linearGradient>
                            ))}
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                        <XAxis
                            dataKey={x_field}
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={x_label ? { value: x_label, position: "insideBottom", offset: -10, fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <YAxis
                            stroke="rgba(255,255,255,0.5)"
                            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
                            label={y_label ? { value: y_label, angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.6)" } : undefined}
                        />
                        <Tooltip
                            contentStyle={{
                                background: "rgba(15, 15, 35, 0.95)",
                                border: "1px solid rgba(99, 102, 241, 0.3)",
                                borderRadius: "12px",
                                color: "#e2e8f0",
                            }}
                        />
                        <Legend wrapperStyle={{ color: "rgba(255,255,255,0.7)" }} />
                        {yFields.map((field, i) => (
                            <Area
                                key={field}
                                type="monotone"
                                dataKey={field}
                                stroke={palette[i % palette.length]}
                                strokeWidth={2}
                                fill={`url(#gradient-${i})`}
                            />
                        ))}
                    </AreaChart>
                );

            default:
                return (
                    <div className="chart-empty">
                        <p>Unsupported chart type: {chartType}</p>
                    </div>
                );
        }
    };

    return (
        <div className="chart-wrapper">
            {title && <h3 className="chart-title">{title}</h3>}
            <ResponsiveContainer width="100%" height={400}>
                {renderChart()}
            </ResponsiveContainer>
        </div>
    );
}
