import { useId, useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Zoom,
  Tooltip,
  Divider,
  Button,
  Stack,
  Chip,
  Collapse,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { ExpandMore as ExpandMoreIcon, OpenInNew as OpenInNewIcon } from '@mui/icons-material';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Tooltip as RechartsTooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import type { DashboardCardInsight } from '@/types';

interface InteractiveMetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  gradient: string;
  subtitle?: string;
  trendLabel?: string;
  hoverDetails?: string;
  insight?: DashboardCardInsight;
  onDrillDown?: () => void;
  drillDownLabel?: string;
}

interface SparklineTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

const PIE_COLORS = ['#4caf50', '#ff9800', '#2196f3', '#f44336', '#ab47bc', '#26a69a', '#8d6e63'];

function SparklineTooltip({ active, payload, label }: SparklineTooltipProps) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <Box
      sx={{
        bgcolor: 'grey.900',
        color: 'common.white',
        px: 1.5,
        py: 1,
        borderRadius: 1,
        boxShadow: 3,
        fontSize: 12,
      }}
    >
      <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
        {label}
      </Typography>
      <Typography variant="caption">{payload[0].value}</Typography>
    </Box>
  );
}

export default function InteractiveMetricCard({
  title,
  value,
  icon,
  gradient,
  subtitle,
  trendLabel,
  hoverDetails,
  insight,
  onDrillDown,
  drillDownLabel = 'View details',
}: InteractiveMetricCardProps) {
  const [expanded, setExpanded] = useState(false);
  const rawId = useId();
  const chartGradientId = useMemo(() => `sparkline-${rawId.replace(/:/g, '')}`, [rawId]);

  const hasSparkline = Boolean(insight?.sparkline?.length);
  const hasDistribution = Boolean(insight?.distribution?.length);

  const handleToggleExpand = () => {
    if (hasSparkline || hasDistribution) {
      setExpanded((prev) => !prev);
    }
  };

  return (
    <Zoom in timeout={300}>
      <Tooltip title={hoverDetails || ''} placement="top" arrow disableHoverListener={!hoverDetails}>
        <Card
          elevation={0}
          onClick={handleToggleExpand}
          role={hasSparkline || hasDistribution ? 'button' : undefined}
          sx={{
            height: '100%',
            background: gradient,
            color: 'common.white',
            position: 'relative',
            overflow: 'hidden',
            cursor: hasSparkline || hasDistribution ? 'pointer' : 'default',
            transition: 'all 0.3s ease',
            '&:hover': {
              transform: 'translateY(-4px)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
            },
          }}
        >
          <CardContent sx={{ position: 'relative', zIndex: 1 }}>
            <Box display="flex" alignItems="flex-start" justifyContent="space-between" mb={2}>
              <Box>
                <Typography variant="body2" sx={{ opacity: 0.9, fontWeight: 500, mb: 1 }}>
                  {title}
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, mb: 0.5 }}>
                  {value}
                </Typography>
                {subtitle && (
                  <Typography variant="caption" sx={{ opacity: 0.8 }}>
                    {subtitle}
                  </Typography>
                )}
              </Box>
              <Box
                sx={{
                  bgcolor: alpha('#ffffff', 0.2),
                  borderRadius: 2,
                  p: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {icon}
              </Box>
            </Box>

            {trendLabel && (
              <Chip
                label={trendLabel}
                size="small"
                sx={{
                  color: 'common.white',
                  bgcolor: alpha('#000', 0.2),
                  fontSize: 11,
                  height: 22,
                }}
              />
            )}

            {hasSparkline && (
              <Box sx={{ height: 70, mt: 2, mx: -1 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={insight!.sparkline}>
                    <defs>
                      <linearGradient id={chartGradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="10%" stopColor="#ffffff" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#ffffff" stopOpacity={0.1} />
                      </linearGradient>
                    </defs>
                    <RechartsTooltip content={<SparklineTooltip />} cursor={false} />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="#ffffff"
                      strokeWidth={2}
                      fill={`url(#${chartGradientId})`}
                      fillOpacity={1}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Box>
            )}

            {(hasSparkline || hasDistribution) && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 12,
                  right: 12,
                  transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s ease',
                  bgcolor: alpha('#000', 0.2),
                  borderRadius: '50%',
                  width: 28,
                  height: 28,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <ExpandMoreIcon fontSize="small" />
              </Box>
            )}
          </CardContent>

          {(hasSparkline || hasDistribution) && (
            <Collapse in={expanded} timeout="auto" unmountOnExit>
              <Divider sx={{ borderColor: alpha('#ffffff', 0.2) }} />
              <CardContent sx={{ pt: 2 }}>
                <Stack spacing={2}>
                  {hasDistribution && (
                    <Box display="flex" alignItems="center" justifyContent="space-between" gap={2}>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="subtitle2" sx={{ opacity: 0.85, mb: 1 }}>
                          Distribution
                        </Typography>
                        <Stack spacing={1}>
                          {insight!.distribution!.map((item, index) => (
                            <Stack key={item.label} direction="row" spacing={1} alignItems="center">
                              <Box
                                sx={{
                                  width: 10,
                                  height: 10,
                                  borderRadius: '50%',
                                  bgcolor: PIE_COLORS[index % PIE_COLORS.length],
                                }}
                              />
                              <Typography variant="caption" sx={{ opacity: 0.85 }}>
                                {item.label}: <strong>{item.value}</strong>
                              </Typography>
                            </Stack>
                          ))}
                        </Stack>
                      </Box>
                      <Box sx={{ width: 120, height: 120 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={insight!.distribution}
                              dataKey="value"
                              nameKey="label"
                              innerRadius={35}
                              outerRadius={55}
                              paddingAngle={3}
                            >
                              {insight!.distribution!.map((_, index) => (
                                <Cell
                                  key={`slice-${index}`}
                                  fill={PIE_COLORS[index % PIE_COLORS.length]}
                                  stroke="none"
                                />
                              ))}
                            </Pie>
                          </PieChart>
                        </ResponsiveContainer>
                      </Box>
                    </Box>
                  )}

                  {onDrillDown && (
                    <Button
                      variant="contained"
                      color="secondary"
                      size="small"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDrillDown();
                      }}
                      endIcon={<OpenInNewIcon fontSize="small" />}
                      sx={{
                        alignSelf: 'flex-start',
                        bgcolor: alpha('#000', 0.25),
                        color: 'common.white',
                        '&:hover': {
                          bgcolor: alpha('#000', 0.4),
                        },
                      }}
                    >
                      {drillDownLabel}
                    </Button>
                  )}
                </Stack>
              </CardContent>
            </Collapse>
          )}

          {/* Decorative circles */}
          <Box
            sx={{
              position: 'absolute',
              top: -20,
              right: -20,
              width: 100,
              height: 100,
              borderRadius: '50%',
              bgcolor: 'rgba(255, 255, 255, 0.1)',
            }}
          />
          <Box
            sx={{
              position: 'absolute',
              bottom: -30,
              left: -30,
              width: 120,
              height: 120,
              borderRadius: '50%',
              bgcolor: 'rgba(255, 255, 255, 0.05)',
            }}
          />
        </Card>
      </Tooltip>
    </Zoom>
  );
}
