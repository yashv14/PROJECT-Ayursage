import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createPatientWorkspace } from '../patient/workspace.js';
import { ProfileScreen } from './PatientProfilePage.jsx';
import { AssessmentFormScreen } from './AssessmentFormPage.jsx';
import { AssessmentHistoryScreen } from './AssessmentHistoryPage.jsx';
import { AssessmentDetailScreen } from './AssessmentDetailPage.jsx';
import { ClinicalReportPanel } from './ClinicalReportPanel.jsx';

export function PatientWorkspacePage({ page, assessmentId }) {
  const { patients } = useAuth();
  const [workspace] = useState(() => createPatientWorkspace(patients));
  const state = useSyncExternalStore(workspace.subscribe, workspace.getSnapshot, workspace.getSnapshot);
  useEffect(() => {
    const disconnect = workspace.connect();
    workspace.loadProfile();
    return disconnect;
  }, [workspace]);
  useEffect(() => {
    if (state.profile.status !== 'ready' || !state.profile.data) return;
    if (page === 'profile') workspace.loadGrants();
    if (page === 'history') workspace.loadHistory();
    if (page === 'detail') workspace.loadDetail(assessmentId);
  }, [page, assessmentId, state.profile.status, state.profile.data, workspace]);
  if (page === 'profile' || state.profile.status !== 'ready' || !state.profile.data) {
    return <ProfileScreen profile={state.profile} onCreate={workspace.createProfile} onReload={workspace.loadProfile}
      grants={page === 'profile' ? state.grants : undefined} onReloadGrants={() => workspace.loadGrants()}
      onMoreGrants={() => workspace.loadGrants(true)} onConfirmRevoke={workspace.confirmGrantRevocation}
      onCancelRevoke={workspace.cancelGrantRevocation} onRevoke={workspace.revokeGrant} />;
  }
  if (page === 'newAssessment') return <AssessmentFormScreen form={state.form} onField={workspace.changeField} onNotes={workspace.changeNotes} onPredict={workspace.changePredict} onSubmit={workspace.submit} onReset={workspace.resetForm} />;
  if (page === 'history') return <AssessmentHistoryScreen history={state.history} onReload={() => workspace.loadHistory()} onMore={() => workspace.loadHistory(true)} />;
  return <AssessmentDetailScreen detail={state.detail.requestedId === assessmentId ? state.detail : { status: 'loading', data: null, error: '' }} onRetry={() => workspace.loadDetail(assessmentId)}
    reportPanel={<ClinicalReportPanel key={assessmentId} patientId={state.profile.data.id} assessmentId={assessmentId} />} />;
}
