import { useEffect, useMemo, useState } from 'react';
import { addDays, format, parseISO } from 'date-fns';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  Grid,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Switch,
  FormControlLabel,
  Snackbar,
  Alert,
  Chip,
  Stack,
  CircularProgress,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import EventBusyIcon from '@mui/icons-material/EventBusy';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import WatchLaterIcon from '@mui/icons-material/WatchLater';
import DateRangeIcon from '@mui/icons-material/DateRange';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

import apiClient from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import {
  TeamLevel,
  TeamMember,
  ShiftAssignment,
  MemberLeave,
  LeaveStatusEnum,
  LeaveTypeEnum,
} from '@/types';

type TabKey = 'shifts' | 'leaves' | 'availability';

const startOfWeekMonday = (date: Date) => {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  const day = result.getDay();
  const diff = (day + 6) % 7;
  result.setDate(result.getDate() - diff);
  return result;
};

interface OncallAssignment {
  id: number;
  team_level: TeamLevel | string;
  team_member_id: number | null;
  team_member_name: string | null;
  week_start: string;
  week_end: string;
  status: string;
  rotation_position?: number;
  created_at?: string;
}

const dayLabels = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

const hourOptions = Array.from({ length: 24 }).map((_, idx) => idx);
const minuteOptions = [0, 15, 30, 45];

interface ShiftFormState {
  team_member_id: number | '';
  team_level: TeamLevel | '';
  day_of_week: number | null;
  start_hour: number;
  start_minute: number;
  end_hour: number;
  end_minute: number;
  timezone: string;
  effective_from: string;
  effective_to: string;
  priority: number;
  is_active: boolean;
  notes: string;
}

interface LeaveFormState {
  team_member_id: number | '';
  start_date: string;
  end_date: string;
  leave_type: LeaveTypeEnum;
  reason: string;
}

interface GroupedShiftRow {
  id?: number;
  team_member_id?: number | null;
  team_member_name?: string | null;
  team_level?: TeamLevel | string | null;
  timezone?: string;
  is_active?: boolean;
  shifts: ShiftAssignment[];
  [key: string]: unknown;
}

const defaultShiftState: ShiftFormState = {
  team_member_id: '',
  team_level: '',
  day_of_week: 0,
  start_hour: 9,
  start_minute: 0,
  end_hour: 18,
  end_minute: 0,
  timezone: 'Asia/Kolkata',
  effective_from: '',
  effective_to: '',
  priority: 50,
  is_active: true,
  notes: '',
};

const defaultLeaveState: LeaveFormState = {
  team_member_id: '',
  start_date: '',
  end_date: '',
  leave_type: LeaveTypeEnum.VACATION,
  reason: '',
};

const Scheduling = () => {
  const {
    isAdmin,
    isManager,
    isSuperAdmin,
    user,
  } = useAuth();

  const canManageShifts = isSuperAdmin || isAdmin || isManager;
  const canManageLeaves = isSuperAdmin || isAdmin || isManager;

  const [activeTab, setActiveTab] = useState<TabKey>(canManageShifts ? 'shifts' : 'availability');

  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [teamLevelFilter, setTeamLevelFilter] = useState<TeamLevel | 'ALL'>('ALL');
  const [includeInactiveShifts, setIncludeInactiveShifts] = useState(false);
  const [shifts, setShifts] = useState<GroupedShiftRow[]>([]);
  const [loadingShifts, setLoadingShifts] = useState(false);
  const [shiftDialogOpen, setShiftDialogOpen] = useState(false);
  const [shiftForm, setShiftForm] = useState<ShiftFormState>(defaultShiftState);
  const [editingShift, setEditingShift] = useState<ShiftAssignment | null>(null);
  const [editingShiftIds, setEditingShiftIds] = useState<number[]>([]);
  const [groupInitialActive, setGroupInitialActive] = useState<boolean>(true);

  const [leaves, setLeaves] = useState<MemberLeave[]>([]);
  const [myLeaves, setMyLeaves] = useState<MemberLeave[]>([]);
  const [loadingLeaves, setLoadingLeaves] = useState(false);
  const [loadingOncall, setLoadingOncall] = useState(false);
  const [runningOncall, setRunningOncall] = useState(false);
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [leaveForm, setLeaveForm] = useState<LeaveFormState>(defaultLeaveState);
  const [editingLeave, setEditingLeave] = useState<MemberLeave | null>(null);
  const [leaveStatusFilter, setLeaveStatusFilter] = useState<LeaveStatusEnum | 'all'>('all');
  const [oncallAssignments, setOncallAssignments] = useState<OncallAssignment[]>([]);
  const [nextWeekAssignments, setNextWeekAssignments] = useState<OncallAssignment[]>([]);
  const [nextWeekLoading, setNextWeekLoading] = useState(false);
  const [rotationSelection, setRotationSelection] = useState<string>('');
  const [rotationLoadingLevel, setRotationLoadingLevel] = useState<string | null>(null);
  const [replacementAssignmentId, setReplacementAssignmentId] = useState<number | ''>('');
  const [replacementMemberId, setReplacementMemberId] = useState<number | ''>('');
  const [replacementReason, setReplacementReason] = useState('');
  const [replacementLoading, setReplacementLoading] = useState(false);
  const [oncallWeekStart, setOncallWeekStart] = useState<string>(() => {
    const start = startOfWeekMonday(new Date());
    return format(start, 'yyyy-MM-dd');
  });
  const [nextOncallWeekStart, setNextOncallWeekStart] = useState<string>(() => {
    const start = addDays(startOfWeekMonday(new Date()), 7);
    return format(start, 'yyyy-MM-dd');
  });

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const teamLevels = useMemo(() => Object.values(TeamLevel), []);
  const currentMember = useMemo(
    () => teamMembers.find((member) => member.user_id === user?.id) ?? null,
    [teamMembers, user?.id]
  );
  const oncallTeamLevels = useMemo(() => {
    const levels = new Set<string>();
    oncallAssignments.forEach((assignment) => {
      if (assignment.team_level) {
        levels.add(String(assignment.team_level));
      }
    });
    return Array.from(levels);
  }, [oncallAssignments]);
  const isL3Member = useMemo(() => {
    if (!currentMember?.team_level) {
      return false;
    }
    return String(currentMember.team_level) === TeamLevel.L3;
  }, [currentMember]);
  const canDeleteLeaves = isSuperAdmin || isAdmin || isL3Member;
  const canViewLeaves = canManageLeaves || canDeleteLeaves;

  const filteredMembers = useMemo(() => {
    if (teamLevelFilter === 'ALL') {
      return teamMembers;
    }
    return teamMembers.filter((member) => member.team_level === teamLevelFilter);
  }, [teamMembers, teamLevelFilter]);

  const showSnackbar = (message: string, severity: 'success' | 'error' = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const closeSnackbar = () => setSnackbar({ ...snackbar, open: false });

  const extractErrorMessage = (error: any, fallback: string) => {
    const detail = error?.response?.data?.detail ?? error?.message ?? fallback;
    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item?.msg) return item.msg;
          if (item?.detail) return item.detail;
          return JSON.stringify(item);
        })
        .filter(Boolean)
        .join(', ');
      return message || fallback;
    }
    if (typeof detail === 'string') {
      return detail;
    }
    if (typeof detail === 'object' && detail !== null) {
      if (detail.message) {
        return detail.message;
      }
      if (detail.detail) {
        return typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail);
      }
      try {
        return JSON.stringify(detail);
      } catch {
        return fallback;
      }
    }
    return fallback;
  };

  const normalizeBoolean = (value: any): boolean => {
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'string') {
      const lowered = value.toLowerCase();
      return lowered === 'true' || lowered === '1' || lowered === 'yes';
    }
    if (typeof value === 'number') {
      return value !== 0;
    }
    return Boolean(value);
  };

  const loadTeamMembers = async () => {
    try {
      const members = await apiClient.getTeamMembers();
      setTeamMembers(members);
    } catch (error) {
      console.error('Failed to load team members', error);
      showSnackbar('Failed to load team members', 'error');
    }
  };

  const loadShifts = async () => {
    setLoadingShifts(true);
    try {
      const params: Record<string, any> = { grouped: true };
      if (teamLevelFilter !== 'ALL') {
        params.team_level = teamLevelFilter;
      }
      if (includeInactiveShifts) {
        params.include_inactive = true;
      }
      const data = await apiClient.getShiftAssignments(params);
      // Backend already returns grouped data - no need to merge
      const normalized: GroupedShiftRow[] = (data || []).map((entry: any) => ({
        ...entry,
        shifts: Array.isArray(entry.shifts) ? entry.shifts : [],
        is_active: normalizeBoolean(entry.is_active),
      }));
      setShifts(normalized);
    } catch (error) {
      console.error('Failed to load shift assignments', error);
      showSnackbar('Failed to load shift assignments', 'error');
    } finally {
      setLoadingShifts(false);
    }
  };

  const loadLeaves = async () => {
    setLoadingLeaves(true);
    try {
      if (canViewLeaves) {
        const params: Record<string, any> = {};
        if (teamLevelFilter !== 'ALL') {
          params.team_level = teamLevelFilter;
        }
        if (leaveStatusFilter !== 'all') {
          params.status = leaveStatusFilter;
        }
        const data = await apiClient.getLeaves(params);
        setLeaves(data);
      } else {
        setLeaves([]);
      }
      const myData = await apiClient.getMyLeaves(true);
      setMyLeaves(myData);
    } catch (error) {
      console.error('Failed to load leaves', error);
      showSnackbar('Failed to load leave entries', 'error');
    } finally {
      setLoadingLeaves(false);
    }
  };

  const loadOncallAssignments = async () => {
    setLoadingOncall(true);
    try {
      const assignments = await apiClient.getOncallAssignments(oncallWeekStart);
      setOncallAssignments(assignments);
    } catch (error) {
      console.error('Failed to load on-call assignments', error);
      showSnackbar('Failed to load on-call assignments', 'error');
    } finally {
      setLoadingOncall(false);
    }
  };

  const loadNextWeekAssignments = async () => {
    setNextWeekLoading(true);
    try {
      const assignments = await apiClient.getOncallAssignments(nextOncallWeekStart);
      setNextWeekAssignments(assignments);
    } catch (error) {
      console.error('Failed to load upcoming on-call assignments', error);
      showSnackbar('Failed to load upcoming on-call assignments', 'error');
    } finally {
      setNextWeekLoading(false);
    }
  };

  const handleRunOncallAssignments = async (force: boolean = false) => {
    setRunningOncall(true);
    try {
      const assignments = await apiClient.runOncallAssignments(oncallWeekStart, force);
      setOncallAssignments(assignments);
      await loadNextWeekAssignments();
      showSnackbar(force ? 'On-call roster regenerated with force run' : 'On-call roster generated successfully');
    } catch (error: any) {
      console.error('Failed to run on-call assignments', error);
      const message = extractErrorMessage(error, 'Failed to run on-call assignments');
      showSnackbar(message, 'error');
    } finally {
      setRunningOncall(false);
    }
  };

  const handleRotateOncall = async () => {
    if (!rotationSelection) {
      showSnackbar('Select a team level to rotate', 'error');
      return;
    }
    setRotationLoadingLevel(rotationSelection);
    try {
      await apiClient.rotateOncall(rotationSelection, oncallWeekStart);
      await loadOncallAssignments();
      await loadNextWeekAssignments();
      showSnackbar(`On-call rotation updated for ${rotationSelection}`);
    } catch (error: any) {
      console.error('Failed to rotate on-call assignment', error);
      const message = extractErrorMessage(error, 'Failed to rotate on-call assignment');
      showSnackbar(message, 'error');
    } finally {
      setRotationLoadingLevel(null);
    }
  };

  const handleReplaceAssignment = async () => {
    if (!replacementAssignmentId || !replacementMemberId) {
      showSnackbar('Select an assignment and replacement member', 'error');
      return;
    }
    setReplacementLoading(true);
    try {
      await apiClient.replaceOncallAssignment(
        Number(replacementAssignmentId),
        Number(replacementMemberId),
        replacementReason.trim() || undefined,
      );
      setReplacementAssignmentId('');
      setReplacementMemberId('');
      setReplacementReason('');
      await loadOncallAssignments();
      await loadNextWeekAssignments();
      showSnackbar('On-call assignment replaced successfully');
    } catch (error: any) {
      console.error('Failed to replace on-call assignment', error);
      const message = extractErrorMessage(error, 'Failed to replace on-call assignment');
      showSnackbar(message, 'error');
    } finally {
      setReplacementLoading(false);
    }
  };

  useEffect(() => {
    loadTeamMembers();
  }, []);

  useEffect(() => {
    if (activeTab === 'shifts' && canManageShifts) {
      loadShifts();
    }
  }, [activeTab, teamLevelFilter, includeInactiveShifts]);

  useEffect(() => {
    if ((activeTab === 'leaves' && canViewLeaves) || activeTab === 'availability') {
      loadLeaves();
    }
  }, [activeTab, teamLevelFilter, leaveStatusFilter, canViewLeaves]);

  useEffect(() => {
    loadOncallAssignments();
  }, [oncallWeekStart]);

  useEffect(() => {
    loadNextWeekAssignments();
  }, [nextOncallWeekStart]);

  useEffect(() => {
    if (rotationSelection && !oncallTeamLevels.includes(rotationSelection)) {
      setRotationSelection('');
    }
  }, [oncallTeamLevels, rotationSelection]);

  useEffect(() => {
    if (
      replacementAssignmentId &&
      !oncallAssignments.some((assignment) => assignment.id === Number(replacementAssignmentId))
    ) {
      setReplacementAssignmentId('');
    }
  }, [oncallAssignments, replacementAssignmentId]);

  const handleOpenShiftDialog = (
    shift?: ShiftAssignment,
    groupShifts: ShiftAssignment[] = [],
    groupActive?: any,
  ) => {
    if (shift) {
      setEditingShift(shift);
      const ids = groupShifts.length ? groupShifts.map((item) => item.id).filter((id): id is number => typeof id === 'number') : [shift.id];
      setEditingShiftIds(ids);
      const groupActiveValue = groupActive !== undefined ? normalizeBoolean(groupActive) : normalizeBoolean(shift.is_active);
      setGroupInitialActive(groupActiveValue);
      setShiftForm({
        team_member_id: shift.team_member_id,
        team_level: (shift.team_level as TeamLevel) || '',
        day_of_week: shift.day_of_week,
        start_hour: shift.start_hour,
        start_minute: shift.start_minute,
        end_hour: shift.end_hour,
        end_minute: shift.end_minute,
        timezone: shift.timezone,
        effective_from: shift.effective_from ?? '',
        effective_to: shift.effective_to ?? '',
        priority: shift.priority,
        is_active: normalizeBoolean(shift.is_active),
        notes: shift.notes ?? '',
      });
    } else {
      setEditingShift(null);
      setEditingShiftIds([]);
      setGroupInitialActive(true);
      setShiftForm({
        ...defaultShiftState,
        team_level: teamLevelFilter === 'ALL' ? '' : teamLevelFilter,
      });
    }
    setShiftDialogOpen(true);
  };

  const handleCloseShiftDialog = () => {
    setShiftDialogOpen(false);
    setEditingShift(null);
    setShiftForm(defaultShiftState);
    setEditingShiftIds([]);
    setGroupInitialActive(true);
  };

  const handleShiftFormChange = (field: keyof ShiftFormState, value: any) => {
    setShiftForm((prev) => ({
      ...prev,
      [field]: field === 'is_active' ? Boolean(value) : value,
    }));
  };

  const handleSaveShift = async () => {
    if (!shiftForm.team_member_id) {
      showSnackbar('Please select a team member', 'error');
      return;
    }

    const memberId = Number(shiftForm.team_member_id);
    const formPayload: any = {
      ...shiftForm,
      team_member_id: memberId,
    };

    const cleanedPayload: any = { ...formPayload };
    if (!cleanedPayload.team_level) {
      delete cleanedPayload.team_level;
    }
    ['effective_from', 'effective_to', 'notes'].forEach((field) => {
      if (cleanedPayload[field] === '' || cleanedPayload[field] === null) {
        delete cleanedPayload[field];
      }
    });
    if (cleanedPayload.day_of_week === null || cleanedPayload.day_of_week === undefined || cleanedPayload.day_of_week === '') {
      delete cleanedPayload.day_of_week;
    }
    ['start_hour', 'start_minute', 'end_hour', 'end_minute', 'priority'].forEach((field) => {
      if (field in cleanedPayload && cleanedPayload[field] !== '' && cleanedPayload[field] !== null && cleanedPayload[field] !== undefined) {
        cleanedPayload[field] = Number(cleanedPayload[field]);
      }
    });
    if ('is_active' in cleanedPayload) {
      cleanedPayload.is_active = normalizeBoolean(cleanedPayload.is_active);
    }
    if (!cleanedPayload.timezone) {
      delete cleanedPayload.timezone;
    }

    if (!cleanedPayload.team_level) {
      const member = teamMembers.find((m) => m.id === cleanedPayload.team_member_id);
      if (member) {
        cleanedPayload.team_level = member.team_level;
      } else {
        delete cleanedPayload.team_level;
      }
    }

    try {
      if (editingShift) {
        await apiClient.updateShiftAssignment(editingShift.id, cleanedPayload);
        showSnackbar('Shift updated successfully');
        const desiredActive = normalizeBoolean(cleanedPayload.is_active ?? shiftForm.is_active);
        if (editingShiftIds.length > 0 && desiredActive !== groupInitialActive) {
          const otherIds = editingShiftIds.filter((id) => id !== editingShift.id);
          if (otherIds.length) {
            try {
              await Promise.all(
                otherIds.map((shiftId) => apiClient.updateShiftAssignment(shiftId, { is_active: desiredActive })),
              );
            } catch (bulkError: any) {
              console.error('Failed to update related shifts', bulkError);
              const message = extractErrorMessage(bulkError, 'Failed to update related shifts');
              showSnackbar(message, 'error');
              await loadShifts();
              return;
            }
          }
        }
      } else {
        await apiClient.createShiftAssignment(cleanedPayload);
        showSnackbar('Shift created successfully');
      }
      handleCloseShiftDialog();
      loadShifts();
    } catch (error: any) {
      console.error('Failed to save shift', error);
      const message = extractErrorMessage(error, 'Failed to save shift');
      showSnackbar(message, 'error');
    }
  };

  const handleOpenLeaveDialog = (leave?: MemberLeave) => {
    if (leave) {
      setEditingLeave(leave);
      setLeaveForm({
        team_member_id: leave.team_member_id ?? '',
        start_date: leave.start_date,
        end_date: leave.end_date,
        leave_type: leave.leave_type as LeaveTypeEnum,
        reason: leave.reason ?? '',
      });
    } else {
      setEditingLeave(null);
      setLeaveForm({
        ...defaultLeaveState,
        team_member_id: canManageLeaves ? '' : (teamMembers.find((m) => m.user_id === user?.id)?.id ?? ''),
      });
    }
    setLeaveDialogOpen(true);
  };

  const handleCloseLeaveDialog = () => {
    setLeaveDialogOpen(false);
    setEditingLeave(null);
    setLeaveForm(defaultLeaveState);
  };

  const handleLeaveFormChange = (field: keyof LeaveFormState, value: any) => {
    setLeaveForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSaveLeave = async () => {
    const { start_date, end_date, leave_type, reason } = leaveForm;

    if (!start_date || !end_date) {
      showSnackbar('Start and end dates are required', 'error');
      return;
    }

    const payload: any = {
      start_date,
      end_date,
      leave_type,
      reason,
    };

    if (canManageLeaves && leaveForm.team_member_id) {
      payload.team_member_id = leaveForm.team_member_id;
    }

    try {
      if (editingLeave) {
        await apiClient.updateLeave(editingLeave.id, {
          start_date,
          end_date,
          leave_type,
          reason,
        });
        showSnackbar('Leave updated successfully');
      } else {
        const created = await apiClient.createLeave(payload);
        if (created.status === 'pending') {
          showSnackbar('Leave request submitted for approval');
        } else if (created.status === 'approved') {
          showSnackbar('Leave created and approved');
        } else {
          showSnackbar('Leave created successfully');
        }
      }
      handleCloseLeaveDialog();
      loadLeaves();
    } catch (error: any) {
      console.error('Failed to save leave', error);
      const message = error?.response?.data?.detail || 'Failed to save leave';
      showSnackbar(message, 'error');
    }
  };

  const handleApproveLeave = async (leave: MemberLeave, status: LeaveStatusEnum) => {
    try {
      await apiClient.updateLeaveStatus(leave.id, status);
      showSnackbar(`Leave ${status === LeaveStatusEnum.APPROVED ? 'approved' : 'updated'} successfully`);
      loadLeaves();
    } catch (error) {
      console.error('Failed to update leave status', error);
      showSnackbar('Failed to update leave status', 'error');
    }
  };

  const handleDeleteLeave = async (leave: MemberLeave) => {
    const confirmationLabel = leave.team_member_name || 'this member';
    const confirmed = window.confirm(`Delete leave request for ${confirmationLabel}?`);
    if (!confirmed) {
      return;
    }
    try {
      await apiClient.deleteLeave(leave.id);
      showSnackbar('Leave entry deleted', 'success');
      loadLeaves();
    } catch (error) {
      console.error('Failed to delete leave', error);
      showSnackbar('Failed to delete leave', 'error');
    }
  };

  const handleCancelOwnLeave = async (leave: MemberLeave) => {
    try {
      await apiClient.updateLeave(leave.id, { status: LeaveStatusEnum.CANCELLED });
      showSnackbar('Leave cancelled');
      loadLeaves();
    } catch (error) {
      console.error('Failed to cancel leave', error);
      showSnackbar('Failed to cancel leave', 'error');
    }
  };

  const shiftColumns: GridColDef<GroupedShiftRow>[] = [
    {
      field: 'team_member_name',
      headerName: 'Team Member',
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'team_level',
      headerName: 'Level',
      width: 100,
    },
    {
      field: 'shifts',
      headerName: 'Days & Times',
      flex: 2,
      minWidth: 300,
      renderCell: (
        params: GridRenderCellParams<GroupedShiftRow, GroupedShiftRow['shifts']>
      ) => {
        const shiftsValue = params.value ?? [];
        if (shiftsValue.length === 0) return '-';

        // Group by time window
        const timeGroups: Record<string, number[]> = {};
        shiftsValue.forEach((shift: any) => {
          const timeKey = `${formatTime(shift.start_hour, shift.start_minute)} - ${formatTime(shift.end_hour, shift.end_minute)}`;
          if (!timeGroups[timeKey]) {
            timeGroups[timeKey] = [];
          }
          if (shift.day_of_week !== null && shift.day_of_week !== undefined) {
            timeGroups[timeKey].push(shift.day_of_week);
          }
        });

        return (
          <Box sx={{ py: 0.5 }}>
            {Object.entries(timeGroups).map(([timeWindow, days], idx) => (
              <Box key={idx} sx={{ fontSize: '0.875rem', mb: 0.25 }}>
                <strong>{days.sort().map(d => dayLabels[d].slice(0, 3)).join(', ')}:</strong> {timeWindow}
              </Box>
            ))}
          </Box>
        );
      },
    },
    {
      field: 'timezone',
      headerName: 'Timezone',
      width: 150,
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 120,
      renderCell: (
        params: GridRenderCellParams<GroupedShiftRow, GroupedShiftRow['is_active']>
      ) => {
        const active = normalizeBoolean(params.value);
        return (
          <Chip
            label={active ? 'Active' : 'Inactive'}
            color={active ? 'success' : 'default'}
            size="small"
          />
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params: GridRenderCellParams<GroupedShiftRow>) => (
        <Box display="flex" gap={0.5}>
          <Tooltip title="View/Edit Shifts">
            <IconButton size="small" onClick={() => {
              // Show first shift for editing or all shifts
              const rowShifts = params.row?.shifts ?? [];
              if (rowShifts.length > 0) {
                handleOpenShiftDialog(
                  rowShifts[0] as ShiftAssignment,
                  rowShifts as ShiftAssignment[],
                  params.row?.is_active,
                );
              }
            }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  const leaveColumns: GridColDef<MemberLeave>[] = [
    {
      field: 'team_member_name',
      headerName: 'Team Member',
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'team_level',
      headerName: 'Level',
      width: 100,
    },
    {
      field: 'period',
      headerName: 'Period',
      flex: 1,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams<MemberLeave>) => (
        <Typography variant="body2">
          {`${params.row.start_date} → ${params.row.end_date}`}
        </Typography>
      ),
      sortable: false,
    },
    {
      field: 'leave_type',
      headerName: 'Type',
      width: 140,
      renderCell: (
        params: GridRenderCellParams<MemberLeave, MemberLeave['leave_type']>
      ) => (
        <Chip label={params.value} size="small" />
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 140,
      renderCell: (
        params: GridRenderCellParams<MemberLeave, MemberLeave['status']>
      ) => (
        <Chip
          label={params.value}
          size="small"
          color={
            params.value === LeaveStatusEnum.APPROVED
              ? 'success'
              : params.value === LeaveStatusEnum.REJECTED
                ? 'error'
                : params.value === LeaveStatusEnum.CANCELLED
                  ? 'default'
                  : 'warning'
          }
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 200,
      sortable: false,
      renderCell: (params: GridRenderCellParams<MemberLeave>) =>
        renderLeaveActions(params.row),
    },
  ];

  const renderLeaveActions = (leave: MemberLeave) => {
    const isOwnLeave = leave.team_member_id === teamMembers.find((m) => m.user_id === user?.id)?.id;
    const actions: JSX.Element[] = [];

    if (canManageLeaves) {
      if (leave.status === LeaveStatusEnum.PENDING || leave.status === LeaveStatusEnum.APPROVED) {
        actions.push(
          <Tooltip title="Approve" key="approve">
            <IconButton size="small" color="success" onClick={() => handleApproveLeave(leave, LeaveStatusEnum.APPROVED)}>
              <CheckCircleIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      }
      if (leave.status === LeaveStatusEnum.PENDING) {
        actions.push(
          <Tooltip title="Reject" key="reject">
            <IconButton size="small" color="error" onClick={() => handleApproveLeave(leave, LeaveStatusEnum.REJECTED)}>
              <CancelIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      }
      actions.push(
        <Tooltip title="Edit" key="edit">
          <IconButton size="small" onClick={() => handleOpenLeaveDialog(leave)}>
            <EditIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      );
    } else if (!canDeleteLeaves && isOwnLeave && leave.status !== LeaveStatusEnum.CANCELLED) {
      actions.push(
        <Tooltip title="Cancel Leave" key="cancel">
          <IconButton size="small" color="warning" onClick={() => handleCancelOwnLeave(leave)}>
            <EventBusyIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      );
    }

    if (canDeleteLeaves) {
      actions.push(
        <Tooltip title="Delete" key="delete">
          <IconButton size="small" color="error" onClick={() => handleDeleteLeave(leave)}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      );
    }

    return <Box display="flex" gap={0.5}>{actions}</Box>;
  };

  const getStatusColor = (status?: string) => {
    if (!status) {
      return 'default' as const;
    }
    const normalized = status.toLowerCase();
    if (normalized === 'active') {
      return 'success' as const;
    }
    if (normalized === 'pending' || normalized === 'scheduled') {
      return 'warning' as const;
    }
    if (normalized === 'cancelled' || normalized === 'canceled') {
      return 'error' as const;
    }
    if (normalized === 'completed') {
      return 'default' as const;
    }
    return 'info' as const;
  };

  const renderAssignments = (assignments: OncallAssignment[]) => {
    if (!assignments.length) {
      return (
        <Typography variant="body2" color="text.secondary" mt={2}>
          No on-call assignments scheduled for the selected week.
        </Typography>
      );
    }

    return (
      <Grid container spacing={2} mt={1}>
        {assignments.map((assignment) => {
          const startLabel = assignment.week_start ? format(parseISO(assignment.week_start), 'MMM d, yyyy') : 'N/A';
          const endLabel = assignment.week_end ? format(parseISO(assignment.week_end), 'MMM d, yyyy') : 'N/A';
          const chipColor = getStatusColor(assignment.status);
          return (
            <Grid item xs={12} sm={6} md={4} key={`${assignment.team_level}-${assignment.id}`}>
              <Box
                border="1px solid"
                borderColor="divider"
                borderRadius={2}
                p={2}
                display="flex"
                flexDirection="column"
                gap={1}
              >
                <Box display="flex" alignItems="center" gap={1}>
                  <Chip label={assignment.team_level} size="small" color="primary" />
                  {assignment.status && <Chip label={assignment.status} size="small" color={chipColor} />}
                </Box>
                <Typography variant="h6">
                  {assignment.team_member_name || 'Unassigned'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {startLabel} – {endLabel}
                </Typography>
                {typeof assignment.rotation_position === 'number' && (
                  <Typography variant="caption" color="text.secondary">
                    Rotation order #{assignment.rotation_position + 1}
                  </Typography>
                )}
              </Box>
            </Grid>
          );
        })}
      </Grid>
    );
  };

  const rotationInProgress = rotationLoadingLevel !== null && rotationLoadingLevel === rotationSelection;

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4">Scheduling & Availability</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage shift rotations, on-call coverage, and leave schedules.
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          {activeTab === 'shifts' && canManageShifts && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenShiftDialog()}>
              Add Shift
            </Button>
          )}
          {((activeTab === 'leaves' && canManageLeaves) || activeTab === 'availability') && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenLeaveDialog()}>
              Request Leave
            </Button>
          )}
        </Box>
      </Box>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box
            display="flex"
            flexDirection={{ xs: 'column', md: 'row' }}
            justifyContent="space-between"
            alignItems={{ xs: 'flex-start', md: 'center' }}
            gap={2}
          >
            <Box>
              <Typography variant="h6" display="flex" alignItems="center" gap={1}>
                <SupportAgentIcon fontSize="small" />
                On-call Roster
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Review coverage for the selected week. Managers can adjust rotations and force reruns.
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={2} mt={1}>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Current Week Start"
                type="date"
                value={oncallWeekStart}
                onChange={(event) => setOncallWeekStart(event.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Upcoming Week Start"
                type="date"
                value={nextOncallWeekStart}
                onChange={(event) => setNextOncallWeekStart(event.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                {canManageShifts && (
                  <>
                    <Button
                      variant="contained"
                      startIcon={runningOncall ? <CircularProgress size={18} color="inherit" /> : <WatchLaterIcon />}
                      onClick={() => handleRunOncallAssignments(false)}
                      disabled={runningOncall}
                    >
                      {runningOncall ? 'Running...' : 'Run Roster'}
                    </Button>
                    <Button
                      variant="outlined"
                      color="warning"
                      startIcon={runningOncall ? <CircularProgress size={18} color="inherit" /> : <RestartAltIcon />}
                      onClick={() => handleRunOncallAssignments(true)}
                      disabled={runningOncall}
                    >
                      {runningOncall ? 'Force Running...' : 'Force Re-run'}
                    </Button>
                  </>
                )}
                <Button
                  variant="text"
                  onClick={() => {
                    loadOncallAssignments();
                    loadNextWeekAssignments();
                  }}
                  disabled={loadingOncall || nextWeekLoading}
                >
                  Refresh
                </Button>
              </Stack>
            </Grid>
          </Grid>

          <Box mt={3}>
            <Typography variant="subtitle1" display="flex" alignItems="center" gap={1}>
              <DateRangeIcon fontSize="small" />
              Current Coverage
            </Typography>
            {loadingOncall ? (
              <Stack direction="row" alignItems="center" spacing={1} mt={2}>
                <CircularProgress size={20} />
                <Typography variant="body2" color="text.secondary">Loading current roster...</Typography>
              </Stack>
            ) : (
              renderAssignments(oncallAssignments)
            )}
          </Box>

          <Box mt={3}>
            <Typography variant="subtitle1" display="flex" alignItems="center" gap={1}>
              <WatchLaterIcon fontSize="small" />
              Upcoming Week Preview
            </Typography>
            {nextWeekLoading ? (
              <Stack direction="row" alignItems="center" spacing={1} mt={2}>
                <CircularProgress size={20} />
                <Typography variant="body2" color="text.secondary">Loading upcoming roster...</Typography>
              </Stack>
            ) : (
              renderAssignments(nextWeekAssignments)
            )}
          </Box>

          {canManageShifts ? (
            <Box mt={3}>
              <Typography variant="subtitle1" display="flex" alignItems="center" gap={1}>
                <SwapHorizIcon fontSize="small" />
                Manual Adjustments
              </Typography>
              <Grid container spacing={2} mt={1}>
                {oncallTeamLevels.length === 0 && (
                  <Grid item xs={12}>
                    <Alert severity="info">
                      Generate a roster for the selected week to enable manual rotation and replacement options.
                    </Alert>
                  </Grid>
                )}
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel id="rotation-team-level-label">Team Level</InputLabel>
                    <Select
                      labelId="rotation-team-level-label"
                      label="Team Level"
                      value={rotationSelection}
                      onChange={(event) => setRotationSelection(event.target.value as string)}
                      disabled={oncallTeamLevels.length === 0 || rotationInProgress}
                    >
                      <MenuItem value="">
                        <em>Select team level</em>
                      </MenuItem>
                      {oncallTeamLevels.map((level) => (
                        <MenuItem key={level} value={level}>{level}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={rotationInProgress ? <CircularProgress size={18} color="inherit" /> : <SwapHorizIcon />}
                    onClick={handleRotateOncall}
                    disabled={!rotationSelection || rotationInProgress}
                  >
                    {rotationInProgress ? 'Rotating...' : 'Rotate Selected'}
                  </Button>
                </Grid>
                <Grid item xs={12} md={5}>
                  <Typography variant="body2" color="text.secondary">
                    Rotate to the next engineer in the configured order for the selected level.
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel id="replace-assignment-label">Assignment</InputLabel>
                    <Select
                      labelId="replace-assignment-label"
                      label="Assignment"
                      value={replacementAssignmentId}
                      onChange={(event) => setReplacementAssignmentId(
                        event.target.value === '' ? '' : Number(event.target.value)
                      )}
                      disabled={oncallAssignments.length === 0}
                    >
                      <MenuItem value="">
                        <em>Select assignment</em>
                      </MenuItem>
                      {oncallAssignments.map((assignment) => (
                        <MenuItem key={assignment.id} value={assignment.id}>
                          {assignment.team_level}: {assignment.team_member_name || 'Unassigned'}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth>
                    <InputLabel id="replace-member-label">Replacement Engineer</InputLabel>
                    <Select
                      labelId="replace-member-label"
                      label="Replacement Engineer"
                      value={replacementMemberId}
                      onChange={(event) => setReplacementMemberId(
                        event.target.value === '' ? '' : Number(event.target.value)
                      )}
                    >
                      <MenuItem value="">
                        <em>Select member</em>
                      </MenuItem>
                      {teamMembers.map((member) => (
                        <MenuItem key={member.id} value={member.id}>
                          {member.name} ({member.team_level})
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    fullWidth
                    label="Reason (optional)"
                    value={replacementReason}
                    onChange={(event) => setReplacementReason(event.target.value)}
                  />
                </Grid>
                <Grid item xs={12}>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    spacing={1}
                    alignItems={{ xs: 'stretch', sm: 'center' }}
                  >
                    <Button
                      variant="contained"
                      color="secondary"
                      startIcon={replacementLoading ? <CircularProgress size={18} color="inherit" /> : <SupportAgentIcon />}
                      onClick={handleReplaceAssignment}
                      disabled={
                        replacementLoading ||
                        !replacementAssignmentId ||
                        !replacementMemberId
                      }
                    >
                      {replacementLoading ? 'Updating...' : 'Replace Assignment'}
                    </Button>
                    <Typography variant="caption" color="text.secondary">
                      Use when the scheduled engineer is unavailable for their slot.
                    </Typography>
                  </Stack>
                </Grid>
              </Grid>
            </Box>
          ) : (
            <Box mt={3}>
              <Alert severity="info">
                Contact your manager if the on-call roster needs an adjustment.
              </Alert>
            </Box>
          )}
        </CardContent>
      </Card>

      <Tabs
        value={activeTab}
        onChange={(_, value: TabKey) => setActiveTab(value)}
        sx={{ mb: 3 }}
      >
        {canManageShifts && <Tab label="Shift Planner" value="shifts" />}
        {canViewLeaves && <Tab label="Team Leave" value="leaves" />}
        <Tab label="My Availability" value="availability" />
      </Tabs>

      {activeTab === 'shifts' && canManageShifts && (
        <>
          <Card>
            <CardContent>
              <Box display="flex" flexDirection={{ xs: 'column', md: 'row' }} gap={2} mb={2}>
                <FormControl sx={{ minWidth: 180 }}>
                  <InputLabel id="team-level-label">Team Level</InputLabel>
                  <Select
                    labelId="team-level-label"
                    label="Team Level"
                    value={teamLevelFilter}
                    onChange={(event) => setTeamLevelFilter(event.target.value as TeamLevel | 'ALL')}
                  >
                    <MenuItem value="ALL">All Levels</MenuItem>
                    {teamLevels.map((level) => (
                      <MenuItem key={level} value={level}>{level}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControlLabel
                  control={
                    <Switch
                      checked={includeInactiveShifts}
                      onChange={(event) => setIncludeInactiveShifts(event.target.checked)}
                    />
                  }
                  label="Include inactive shifts"
                />
              </Box>

              <DataGrid
                rows={shifts}
                columns={shiftColumns}
                getRowId={(row) => {
                  if (typeof row.id === 'number' || typeof row.id === 'string') {
                    return row.id
                  }
                  if (
                    typeof row.team_member_id === 'number' ||
                    typeof row.team_member_id === 'string'
                  ) {
                    return row.team_member_id
                  }
                  return `shift-${row.team_member_name ?? Math.random().toString(36).slice(2)}`
                }}
                autoHeight
                loading={loadingShifts}
                disableRowSelectionOnClick
                pageSizeOptions={[10, 25, 50]}
                initialState={{
                  pagination: {
                    paginationModel: { pageSize: 10, page: 0 },
                  },
                }}
              />
            </CardContent>
          </Card>
        </>
      )}

      {activeTab === 'leaves' && canViewLeaves && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Box display="flex" gap={2} flexWrap="wrap" mb={2}>
              <FormControl sx={{ minWidth: 180 }}>
                <InputLabel id="leave-team-level-label">Team Level</InputLabel>
                <Select
                  labelId="leave-team-level-label"
                  label="Team Level"
                  value={teamLevelFilter}
                  onChange={(event) => setTeamLevelFilter(event.target.value as TeamLevel | 'ALL')}
                >
                  <MenuItem value="ALL">All Levels</MenuItem>
                  {teamLevels.map((level) => (
                    <MenuItem key={level} value={level}>{level}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 180 }}>
                <InputLabel id="leave-status-label">Status</InputLabel>
                <Select
                  labelId="leave-status-label"
                  label="Status"
                  value={leaveStatusFilter}
                  onChange={(event) => setLeaveStatusFilter(event.target.value as LeaveStatusEnum | 'all')}
                >
                  <MenuItem value="all">All</MenuItem>
                  {Object.values(LeaveStatusEnum).map((status) => (
                    <MenuItem key={status} value={status}>{status}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <DataGrid
              rows={leaves}
              columns={leaveColumns}
              autoHeight
              loading={loadingLeaves}
              disableRowSelectionOnClick
              pageSizeOptions={[10, 25, 50]}
              initialState={{
                pagination: {
                  paginationModel: { pageSize: 10, page: 0 },
                },
              }}
            />
          </CardContent>
        </Card>
      )}

      {activeTab === 'availability' && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom display="flex" alignItems="center" gap={1}>
              <EventAvailableIcon fontSize="small" />
              My Upcoming Leave
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              Submit your planned leave or mark unavailability so the assignment engine can skip you automatically.
            </Typography>
            <DataGrid
              rows={myLeaves}
              columns={[
                { field: 'start_date', headerName: 'Start', width: 130 },
                { field: 'end_date', headerName: 'End', width: 130 },
                { field: 'leave_type', headerName: 'Type', width: 120 },
                {
                  field: 'status',
                  headerName: 'Status',
                  width: 120,
                  renderCell: (params) => (
                    <Chip label={params.value} size="small" color={params.value === LeaveStatusEnum.APPROVED ? 'success' : 'warning'} />
                  ),
                },
                {
                  field: 'actions',
                  headerName: 'Actions',
                  width: 140,
                  sortable: false,
                  renderCell: (params) => renderLeaveActions(params.row),
                },
              ]}
              autoHeight
              loading={loadingLeaves}
              disableRowSelectionOnClick
              pageSizeOptions={[10, 25]}
              initialState={{
                pagination: {
                  paginationModel: { pageSize: 10, page: 0 },
                },
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Shift Dialog */}
      <Dialog open={shiftDialogOpen} onClose={handleCloseShiftDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingShift ? 'Edit Shift Assignment' : 'Add Shift Assignment'}</DialogTitle>
        <DialogContent>
          <Box component="form" mt={1}>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <FormControl fullWidth>
                  <InputLabel id="shift-member-label">Team Member</InputLabel>
                  <Select
                    labelId="shift-member-label"
                    label="Team Member"
                    value={shiftForm.team_member_id}
                    onChange={(event) => handleShiftFormChange('team_member_id', event.target.value)}
                  >
                    {filteredMembers.map((member) => (
                      <MenuItem key={member.id} value={member.id}>
                        {member.name} ({member.team_level})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="shift-team-level-label">Team Level</InputLabel>
                  <Select
                    labelId="shift-team-level-label"
                    label="Team Level"
                    value={shiftForm.team_level}
                    onChange={(event) => handleShiftFormChange('team_level', event.target.value)}
                  >
                    <MenuItem value="">Auto</MenuItem>
                    {teamLevels.map((level) => (
                      <MenuItem key={level} value={level}>{level}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="shift-day-label">Day of Week</InputLabel>
                  <Select
                    labelId="shift-day-label"
                    label="Day of Week"
                    value={shiftForm.day_of_week ?? ''}
                    onChange={(event) => {
                      const value = event.target.value === '' ? null : Number(event.target.value);
                      handleShiftFormChange('day_of_week', value);
                    }}
                  >
                    <MenuItem value="">All days</MenuItem>
                    {dayLabels.map((label, idx) => (
                      <MenuItem key={label} value={idx}>{label}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="start-hour-label">Start Hour</InputLabel>
                  <Select
                    labelId="start-hour-label"
                    label="Start Hour"
                    value={shiftForm.start_hour}
                    onChange={(event) => handleShiftFormChange('start_hour', Number(event.target.value))}
                  >
                    {hourOptions.map((hour) => (
                      <MenuItem key={hour} value={hour}>{hour.toString().padStart(2, '0')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="start-minute-label">Start Minute</InputLabel>
                  <Select
                    labelId="start-minute-label"
                    label="Start Minute"
                    value={shiftForm.start_minute}
                    onChange={(event) => handleShiftFormChange('start_minute', Number(event.target.value))}
                  >
                    {minuteOptions.map((minute) => (
                      <MenuItem key={minute} value={minute}>{minute.toString().padStart(2, '0')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="end-hour-label">End Hour</InputLabel>
                  <Select
                    labelId="end-hour-label"
                    label="End Hour"
                    value={shiftForm.end_hour}
                    onChange={(event) => handleShiftFormChange('end_hour', Number(event.target.value))}
                  >
                    {hourOptions.map((hour) => (
                      <MenuItem key={hour} value={hour}>{hour.toString().padStart(2, '0')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="end-minute-label">End Minute</InputLabel>
                  <Select
                    labelId="end-minute-label"
                    label="End Minute"
                    value={shiftForm.end_minute}
                    onChange={(event) => handleShiftFormChange('end_minute', Number(event.target.value))}
                  >
                    {minuteOptions.map((minute) => (
                      <MenuItem key={minute} value={minute}>{minute.toString().padStart(2, '0')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Timezone"
                  value={shiftForm.timezone}
                  onChange={(event) => handleShiftFormChange('timezone', event.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Priority"
                  type="number"
                  value={shiftForm.priority}
                  onChange={(event) => handleShiftFormChange('priority', Number(event.target.value))}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Effective From"
                  type="date"
                  value={shiftForm.effective_from}
                  onChange={(event) => handleShiftFormChange('effective_from', event.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Effective To"
                  type="date"
                  value={shiftForm.effective_to}
                  onChange={(event) => handleShiftFormChange('effective_to', event.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Notes"
                  value={shiftForm.notes}
                  onChange={(event) => handleShiftFormChange('notes', event.target.value)}
                  multiline
                  minRows={2}
                />
              </Grid>
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={shiftForm.is_active}
                      onChange={(event) => handleShiftFormChange('is_active', event.target.checked)}
                    />
                  }
                  label={editingShift && editingShiftIds.length > 1 ? `Active (applies to all ${editingShiftIds.length} shifts for this member)` : "Active"}
                />
                {editingShift && editingShiftIds.length > 1 && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    Changing this will update all {editingShiftIds.length} shifts for {shiftForm.team_member_id ? teamMembers.find(m => m.id === shiftForm.team_member_id)?.name : 'this member'}.
                    When inactive, no tickets will be routed to this member.
                  </Typography>
                )}
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Box sx={{ display: 'flex', width: '100%', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              {editingShift && editingShiftIds.length > 0 && (
                <Tooltip title="Deactivate all shifts for this member (e.g., for forgotten leave)">
                  <Button
                    color="warning"
                    onClick={async () => {
                      if (!window.confirm(`Deactivate all ${editingShiftIds.length} shift(s) for this member?`)) {
                        return;
                      }
                      try {
                        await Promise.all(
                          editingShiftIds.map((id) =>
                            apiClient.updateShiftAssignment(id, { is_active: false })
                          )
                        );
                        showSnackbar('All shifts deactivated successfully');
                        handleCloseShiftDialog();
                        loadShifts();
                      } catch (error) {
                        console.error('Failed to deactivate shifts', error);
                        showSnackbar('Failed to deactivate all shifts', 'error');
                      }
                    }}
                  >
                    Deactivate All Shifts
                  </Button>
                </Tooltip>
              )}
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button onClick={handleCloseShiftDialog}>Cancel</Button>
              <Button variant="contained" onClick={handleSaveShift}>Save</Button>
            </Box>
          </Box>
        </DialogActions>
      </Dialog>

      {/* Leave Dialog */}
      <Dialog open={leaveDialogOpen} onClose={handleCloseLeaveDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingLeave ? 'Update Leave' : 'Request Leave'}</DialogTitle>
        <DialogContent>
          {!canManageLeaves && !editingLeave && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Your leave request will be submitted for approval. You will be notified once it's reviewed by your manager or admin.
              No tickets will be assigned to you during pending or approved leave periods.
            </Alert>
          )}
          <Box component="form" mt={1}>
            <Grid container spacing={2}>
              {canManageLeaves && (
                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel id="leave-member-label">Team Member</InputLabel>
                    <Select
                      labelId="leave-member-label"
                      label="Team Member"
                      value={leaveForm.team_member_id}
                      onChange={(event) => handleLeaveFormChange('team_member_id', event.target.value)}
                    >
                      {teamMembers.map((member) => (
                        <MenuItem key={member.id} value={member.id}>
                          {member.name} ({member.team_level})
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
              )}
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Start Date"
                  type="date"
                  value={leaveForm.start_date}
                  onChange={(event) => handleLeaveFormChange('start_date', event.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="End Date"
                  type="date"
                  value={leaveForm.end_date}
                  onChange={(event) => handleLeaveFormChange('end_date', event.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel id="leave-type-label">Leave Type</InputLabel>
                  <Select
                    labelId="leave-type-label"
                    label="Leave Type"
                    value={leaveForm.leave_type}
                    onChange={(event) => handleLeaveFormChange('leave_type', event.target.value as LeaveTypeEnum)}
                  >
                    {Object.values(LeaveTypeEnum).map((type) => (
                      <MenuItem key={type} value={type}>{type}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Reason / Notes"
                  value={leaveForm.reason}
                  onChange={(event) => handleLeaveFormChange('reason', event.target.value)}
                  multiline
                  minRows={2}
                />
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseLeaveDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveLeave}>Save</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={closeSnackbar}>
        <Alert severity={snackbar.severity} onClose={closeSnackbar} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

function formatTime(hour: number, minute: number) {
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalizedHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalizedHour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')} ${suffix}`;
}

export default Scheduling;
