import { useEffect, useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  Stack,
  Autocomplete,
  TextField,
  Chip,
  Box,
  Typography,
  Button,
  Divider,
  IconButton,
  Tooltip,
} from '@mui/material';
import SaveAltIcon from '@mui/icons-material/SaveAlt';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import type { AdvancedTicketFilters, TeamMember } from '@/types';

const STATUS_OPTIONS = [
  { value: 'new', label: 'New' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'pending', label: 'Pending Customer' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'reopened', label: 'Reopened' },
  { value: 'escalated', label: 'Escalated' },
];

const PRIORITY_OPTIONS = [
  { value: 'P1', label: 'P1 (Critical)' },
  { value: 'P2', label: 'P2 (High)' },
  { value: 'P3', label: 'P3 (Medium)' },
  { value: 'P4', label: 'P4 (Low)' },
  { value: 'P5', label: 'P5 (Trivial)' },
];

const TEAM_LEVEL_OPTIONS = [
  { value: 'L1', label: 'L1 - Frontline' },
  { value: 'L2', label: 'L2 - Specialist' },
  { value: 'L3', label: 'L3 - Expert' },
];

const SLA_STATUS_OPTIONS = [
  { value: 'within_sla', label: 'Within SLA' },
  { value: 'at_risk', label: 'At Risk' },
  { value: 'critical', label: 'Critical' },
  { value: 'breached', label: 'Breached' },
  { value: 'paused', label: 'Paused' },
  { value: 'met', label: 'Met' },
];

const CATEGORY_OPTIONS = [
  { value: 'kubernetes', label: 'Kubernetes' },
  { value: 'database', label: 'Database' },
  { value: 'network', label: 'Network' },
  { value: 'cicd', label: 'CI/CD' },
  { value: 'messaging', label: 'Messaging' },
  { value: 'storage', label: 'Storage' },
  { value: 'application', label: 'Application' },
  { value: 'security', label: 'Security' },
  { value: 'other', label: 'Other' },
];

const STORAGE_KEY = 'ticket-monitoring.saved-filters';

type SavedFilterRecord = {
  id: string;
  name: string;
  filters: AdvancedTicketFilters;
  created_at: string;
};

const cloneFilters = (input: AdvancedTicketFilters): AdvancedTicketFilters => ({
  statuses: [...input.statuses],
  priorities: [...input.priorities],
  teamLevels: [...input.teamLevels],
  slaStatuses: [...input.slaStatuses],
  assignedToIds: [...input.assignedToIds],
  categories: [...input.categories],
  dateFrom: input.dateFrom,
  dateTo: input.dateTo,
  ticketNumber: input.ticketNumber,
  filterId: input.filterId,
});

interface TicketFilterPanelProps {
  filters: AdvancedTicketFilters;
  onFiltersChange: (filters: AdvancedTicketFilters) => void;
  onClear: () => void;
  teamMembers: TeamMember[];
  loadingMembers?: boolean;
}

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `saved-filter-${Date.now()}`;
}

const toDateInputValue = (value: string | null) => value ?? '';

export default function TicketFilterPanel({
  filters,
  onFiltersChange,
  onClear,
  teamMembers,
  loadingMembers = false,
}: TicketFilterPanelProps) {
  const [savedFilterName, setSavedFilterName] = useState('');
  const [savedFilters, setSavedFilters] = useState<SavedFilterRecord[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return [];
      const parsed = JSON.parse(stored) as SavedFilterRecord[];
      if (!Array.isArray(parsed)) return [];
      return parsed;
    } catch {
      return [];
    }
  });
  const [selectedSavedFilterId, setSelectedSavedFilterId] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedFilters));
    }
  }, [savedFilters]);

  const teamMemberOptions = useMemo(
    () =>
      teamMembers.map((member) => ({
        id: member.id,
        label: member.name,
        teamLevel: member.team_level,
      })),
    [teamMembers]
  );

  const selectedTeamMembers = useMemo(
    () => teamMemberOptions.filter((option) => filters.assignedToIds.includes(option.id)),
    [filters.assignedToIds, teamMemberOptions]
  );

  const mapOptions = <T extends { value: string; label: string }>(options: T[], values: string[]) =>
    options.filter((option) => values.includes(option.value));

  const handleOptionChange = (key: keyof AdvancedTicketFilters, value: any) => {
    onFiltersChange({
      ...filters,
      [key]: value,
    });
  };

  const handleSaveFilter = () => {
    if (!savedFilterName.trim()) return;
    const record: SavedFilterRecord = {
      id: createId(),
      name: savedFilterName.trim(),
      filters: cloneFilters(filters),
      created_at: new Date().toISOString(),
    };
    setSavedFilters((prev) => [record, ...prev]);
    setSavedFilterName('');
    setSelectedSavedFilterId(record.id);
  };

  const handleApplySavedFilter = () => {
    if (!selectedSavedFilterId) return;
    const record = savedFilters.find((item) => item.id === selectedSavedFilterId);
    if (!record) return;
    onFiltersChange(cloneFilters(record.filters));
  };

  const handleDeleteSavedFilter = () => {
    if (!selectedSavedFilterId) return;
    setSavedFilters((prev) => prev.filter((item) => item.id !== selectedSavedFilterId));
    setSelectedSavedFilterId('');
  };

  const statusTags = mapOptions(STATUS_OPTIONS, filters.statuses);
  const priorityTags = mapOptions(PRIORITY_OPTIONS, filters.priorities);
  const teamLevelTags = mapOptions(TEAM_LEVEL_OPTIONS, filters.teamLevels);
  const slaTags = mapOptions(SLA_STATUS_OPTIONS, filters.slaStatuses);
  const categoryTags = mapOptions(CATEGORY_OPTIONS, filters.categories);

  const hasActiveFilters =
    statusTags.length > 0 ||
    priorityTags.length > 0 ||
    teamLevelTags.length > 0 ||
    slaTags.length > 0 ||
    categoryTags.length > 0 ||
    selectedTeamMembers.length > 0 ||
    filters.dateFrom ||
    filters.dateTo ||
    (filters.ticketNumber && filters.ticketNumber.trim());

  return (
    <Card sx={{ mb: 4, boxShadow: 2, borderRadius: 3 }}>
      <CardContent sx={{ p: 3 }}>
        <Stack spacing={3}>
          <Typography variant="h5" fontWeight={600} color="primary.main">
            Filters &amp; Query Builder
          </Typography>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <Autocomplete
              multiple
              disableCloseOnSelect
              options={STATUS_OPTIONS}
              value={statusTags}
              onChange={(_, selected) => handleOptionChange('statuses', selected.map((option) => option.value))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="Statuses" placeholder="Select statuses" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip {...getTagProps({ index })} label={option.label} color="primary" size="small" />
                ))
              }
            />

            <Autocomplete
              multiple
              disableCloseOnSelect
              options={PRIORITY_OPTIONS}
              value={priorityTags}
              onChange={(_, selected) => handleOptionChange('priorities', selected.map((option) => option.value))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="Priorities" placeholder="Select priorities" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip {...getTagProps({ index })} label={option.label} color="secondary" size="small" />
                ))
              }
            />
          </Stack>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <Autocomplete
              multiple
              disableCloseOnSelect
              options={TEAM_LEVEL_OPTIONS}
              value={teamLevelTags}
              onChange={(_, selected) => handleOptionChange('teamLevels', selected.map((option) => option.value))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="Team Levels" placeholder="Select levels" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip {...getTagProps({ index })} label={option.label} color="info" size="small" />
                ))
              }
            />

            <Autocomplete
              multiple
              disableCloseOnSelect
              options={SLA_STATUS_OPTIONS}
              value={slaTags}
              onChange={(_, selected) => handleOptionChange('slaStatuses', selected.map((option) => option.value))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="SLA Status" placeholder="Select statuses" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip {...getTagProps({ index })} label={option.label} color="warning" size="small" />
                ))
              }
            />
          </Stack>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <Autocomplete
              multiple
              disableCloseOnSelect
              loading={loadingMembers}
              options={teamMemberOptions}
              value={selectedTeamMembers}
              onChange={(_, selected) => handleOptionChange('assignedToIds', selected.map((option) => option.id))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="Assigned To" placeholder="Select members" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip
                    {...getTagProps({ index })}
                    label={`${option.label} (${option.teamLevel})`}
                    color="success"
                    size="small"
                  />
                ))
              }
            />

            <Autocomplete
              multiple
              disableCloseOnSelect
              options={CATEGORY_OPTIONS}
              value={categoryTags}
              onChange={(_, selected) => handleOptionChange('categories', selected.map((option) => option.value))}
              getOptionLabel={(option) => option.label}
              renderInput={(params) => <TextField {...params} label="Categories" placeholder="Select categories" />}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip {...getTagProps({ index })} label={option.label} color="default" size="small" />
                ))
              }
            />
          </Stack>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'stretch', md: 'center' }}>
            <TextField
              label="Ticket Number"
              type="text"
              value={filters.ticketNumber || ''}
              onChange={(event) => handleOptionChange('ticketNumber', event.target.value)}
              placeholder="e.g. 33249"
              helperText="Enter Redmine ticket ID"
              sx={{ minWidth: 200 }}
            />
            <TextField
              label="Created From"
              type="date"
              value={toDateInputValue(filters.dateFrom)}
              onChange={(event) => handleOptionChange('dateFrom', event.target.value || null)}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Created To"
              type="date"
              value={toDateInputValue(filters.dateTo)}
              onChange={(event) => handleOptionChange('dateTo', event.target.value || null)}
              InputLabelProps={{ shrink: true }}
            />
          </Stack>

          <Divider />

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
            <TextField
              label="Save current filter as"
              value={savedFilterName}
              onChange={(event) => setSavedFilterName(event.target.value)}
              placeholder="e.g. P1 at risk backlog"
              sx={{ minWidth: 240 }}
            />
            <Tooltip title="Save current filter selection">
              <span>
                <Button
                  variant="contained"
                  startIcon={<SaveAltIcon />}
                  onClick={handleSaveFilter}
                  disabled={!savedFilterName.trim()}
                >
                  Save Filter
                </Button>
              </span>
            </Tooltip>
            <TextField
              select
              label="Saved Filters"
              value={selectedSavedFilterId}
              onChange={(event) => setSelectedSavedFilterId(event.target.value)}
              sx={{ minWidth: 220 }}
              SelectProps={{ native: true }}
            >
              <option value="">Select saved filter</option>
              {savedFilters.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </TextField>
            <Tooltip title="Apply saved filter">
              <span>
                <Button
                  variant="outlined"
                  startIcon={<PlayCircleIcon />}
                  onClick={handleApplySavedFilter}
                  disabled={!selectedSavedFilterId}
                >
                  Apply
                </Button>
              </span>
            </Tooltip>
            <Tooltip title="Delete saved filter">
              <span>
                <IconButton
                  color="error"
                  onClick={handleDeleteSavedFilter}
                  disabled={!selectedSavedFilterId}
                  size="large"
                >
                  <DeleteForeverIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Clear all filters">
              <IconButton color="primary" onClick={onClear} size="large">
                <ClearAllIcon />
              </IconButton>
            </Tooltip>
          </Stack>

          <Divider />

          <Box
            sx={{
              p: 2.5,
              borderRadius: 2,
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'grey.200',
            }}
          >
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Active Query
            </Typography>
            {!hasActiveFilters ? (
              <Typography variant="body1" color="text.secondary">
                No filters applied. Showing all tickets.
              </Typography>
            ) : (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
                {statusTags.map((option) => (
                  <Chip key={`status-${option.value}`} label={`Status: ${option.label}`} size="small" />
                ))}
                {priorityTags.map((option) => (
                  <Chip
                    key={`priority-${option.value}`}
                    label={`Priority: ${option.label}`}
                    color="secondary"
                    size="small"
                  />
                ))}
                {teamLevelTags.map((option) => (
                  <Chip key={`team-${option.value}`} label={`Level: ${option.label}`} color="info" size="small" />
                ))}
                {slaTags.map((option) => (
                  <Chip key={`sla-${option.value}`} label={`SLA: ${option.label}`} color="warning" size="small" />
                ))}
                {selectedTeamMembers.map((option) => (
                  <Chip
                    key={`member-${option.id}`}
                    label={`Assignee: ${option.label}`}
                    color="success"
                    size="small"
                  />
                ))}
                {categoryTags.map((option) => (
                  <Chip key={`category-${option.value}`} label={`Category: ${option.label}`} size="small" />
                ))}
                {filters.ticketNumber && filters.ticketNumber.trim() && (
                  <Chip
                    label={`Ticket #${filters.ticketNumber}`}
                    color="primary"
                    size="small"
                    variant="filled"
                  />
                )}
                {filters.dateFrom && filters.dateTo && (
                  <Chip
                    label={`Created: ${filters.dateFrom} → ${filters.dateTo}`}
                    color="default"
                    size="small"
                  />
                )}
                {filters.dateFrom && !filters.dateTo && (
                  <Chip label={`Created after ${filters.dateFrom}`} color="default" size="small" />
                )}
                {!filters.dateFrom && filters.dateTo && (
                  <Chip label={`Created before ${filters.dateTo}`} color="default" size="small" />
                )}
              </Stack>
            )}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
