import AppKit
import SwiftUI

struct SpotWorkspaceView: View {
    @ObservedObject var service: SpotCoreService
    @AppStorage("spot.dashboard.topChromeCollapsed") private var topChromeCollapsed: Bool = true

    var body: some View {
        VStack(spacing: 0) {
            topChrome
                .padding(.horizontal, 24)
                .padding(.top, 20)
                .padding(.bottom, 12)

            Divider()

            currentPageContent
        }
        .frame(minWidth: 1320, minHeight: 920)
    }

    private var topChrome: some View {
        VStack(spacing: 12) {
            HStack(spacing: 10) {
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        topChromeCollapsed.toggle()
                    }
                } label: {
                    Label(
                        topChromeCollapsed ? "Show Live Run" : "Hide Live Run",
                        systemImage: topChromeCollapsed ? "sidebar.right" : "sidebar.left"
                    )
                    .labelStyle(.iconOnly)
                }
                .buttonStyle(.bordered)
                .help(topChromeCollapsed ? "Expand the live run bar" : "Collapse the live run bar")

                ForEach(SpotAppPage.allCases) { page in
                    Button(page.title) {
                        service.navigate(to: page)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(service.currentPage == page ? .teal : .gray.opacity(0.35))
                }

                Spacer()

                if topChromeCollapsed {
                    compactRuntimeBadge
                }

                Button("Refresh Runtime") {
                    Task { await service.refreshRuntimeSnapshot() }
                }
            }

            if !topChromeCollapsed {
                SpotLiveProcessStripView(service: service)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }

    private var compactRuntimeBadge: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(compactRuntimeTint)
                .frame(width: 9, height: 9)

            VStack(alignment: .leading, spacing: 2) {
                Text(compactRuntimeTitle)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .lineLimit(1)
                Text(compactRuntimeDetail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(Capsule())
    }

    @ViewBuilder
    private var currentPageContent: some View {
        switch service.currentPage {
        case .dashboard:
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    hero
                    missionRow
                    intakeAndQueueRow
                    runsAndDetailRow
                    validationAndLogs
                }
                .padding(24)
            }
        case .control:
            ScrollView {
                SpotControlCenterView(service: service)
                    .padding(24)
            }
        case .intake:
            ScrollView {
                SpotIntakeWorkspaceView(service: service)
                    .padding(24)
            }
        case .review:
            SpotReviewWorkspaceView(service: service)
                .padding(24)
        case .operations:
            ScrollView {
                SpotArtifactWorkspaceView(service: service)
                    .padding(24)
            }
        }
    }

    private var hero: some View {
        HStack(alignment: .center, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                Text("{spot}")
                    .font(.system(size: 28, weight: .bold, design: .serif))
                Text("Operations Dashboard")
                    .font(.title2)
                    .fontWeight(.semibold)
                Text("Local-first upload, run tracking, review-state visibility, and audit-oriented operator actions for the current `.xlsx` workflow.")
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text("LOCAL OPERATOR SURFACE")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .tracking(1.5)
                    .foregroundStyle(.teal)
                Text("Native local mode")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 18)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    private var missionMetricColumns: [GridItem] {
        Array(repeating: GridItem(.flexible(minimum: 160), spacing: 14), count: 6)
    }

    private var missionHeader: some View {
        GeometryReader { geometry in
            let totalSpacing = CGFloat(14 * 5)
            let cardWidth = max((geometry.size.width - totalSpacing) / 6, 160)
            let leftWidth = cardWidth * 4 + 14 * 3
            let rightWidth = cardWidth * 2 + 14

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("MISSION CONTROL")
                        .font(.headline)
                        .tracking(1.5)
                        .foregroundStyle(.teal)
                    Text("Processing status, operator controls, throughput, and queue pressure for the currently active local workload.")
                        .font(.title3)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 14) {
                        Button("Pause Processing") { Task { await service.performRunOperation("pause") } }
                            .disabled(!service.canPauseActiveRun)
                        Button("Resume Processing") { Task { await service.performRunOperation("resume") } }
                            .disabled(!service.canResumeActiveRun)
                        Button("Stop Run") { Task { await service.performRunOperation("cancel") } }
                            .tint(.orange)
                            .disabled(!service.canCancelActiveRun)
                        Button("Retry Run") { Task { await service.performRunOperation("retry") } }
                            .disabled(!service.canRetrySelectedRun)
                        Button("Recover Run") { Task { await service.performRunOperation("recover") } }
                            .disabled(!service.canRecoverSelectedRun)
                    }
                }
                .frame(width: leftWidth, alignment: .leading)

                VStack(alignment: .leading, spacing: 16) {
                    Text("OPERATIONAL SNAPSHOT")
                        .font(.headline)
                        .tracking(1.5)
                        .foregroundStyle(.teal)
                    Text("A compact readout of intake health, review load, and current queue pressure. This surface should stay readable while a run is in motion.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
                .frame(width: rightWidth, alignment: .leading)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .frame(height: 166, alignment: .topLeading)
    }

    private var missionRow: some View {
        VStack(alignment: .leading, spacing: 16) {
            missionHeader

            LazyVGrid(columns: missionMetricColumns, alignment: .leading, spacing: 14) {
                metricCard("RUN STATE", stateStackValue, stateStackSubline, icon: "gauge.with.dots.needle", series: service.metricHistorySeries(.progressPercent), tint: stateTint(service.activeRunSummary.runState))
                metricCard("PROCESSED ROWS", formattedInt(activeStats?.processedRows ?? service.activeRunProcessedRows), processedRowsSubline, icon: "list.bullet.clipboard", series: service.metricHistorySeries(.processedRows))
                metricCard("TOTAL ROWS", formattedInt(activeStats?.totalRows ?? service.activeRunTotalRows), "Rows accepted for the active run", icon: "square.stack.3d.up", series: service.metricHistorySeries(.totalRows))
                metricCard("ROW PROGRESS", formattedPercent(activeProgressPercent), rowProgressSubline, icon: "chart.line.uptrend.xyaxis", series: service.metricHistorySeries(.progressPercent))
                metricCard("RUN RECORDS", "\(service.availableRuns.count)", "Latest: \(service.availableRuns.first?.runID ?? "none")", icon: "tray.full", series: service.metricHistorySeries(.runRecords))
                metricCard("ACCEPTED WORKBOOKS", acceptedUploadCount, "Validated intake records", icon: "checklist", series: service.metricHistorySeries(.acceptedUploads))
                metricCard("ROWS REMAINING", formattedInt(activeRowsRemaining), "Rows not yet classified", icon: "hourglass.bottomhalf.filled", series: service.metricHistorySeries(.rowsRemaining))
                metricCard("AVERAGE SECONDS PER ROW", formattedDecimal(activeStats?.avgSecondsPerRow), avgSecondsDeltaText, icon: "timer", series: service.metricHistorySeries(.avgSecondsPerRow), tint: avgSecondsTint)
                metricCard("ELAPSED PROCESSING TIME", formattedDuration(activeStats?.elapsedSeconds), "Wall-clock time since run start", icon: "clock.arrow.circlepath", series: service.metricHistorySeries(.elapsedSeconds))
                metricCard("REVIEW-REQUIRED ROWS", formattedInt(activeReviewRequiredRows), reviewRateDeltaText, icon: "flag.badge.ellipsis", series: service.metricHistorySeries(.reviewRequiredRows), tint: reviewRateTint)
                metricCard("PENDING REVIEW ROWS", "\(service.pendingReviewCount)", "Rows awaiting reviewer action", icon: "exclamationmark.bubble", series: service.metricHistorySeries(.pendingReviewRows))
                metricCard("SEGMENT QUEUE", overviewSegmentCount, overviewSegmentHealth, icon: "square.3.layers.3d.down.right", series: service.metricHistorySeries(.segmentQueue))
            }

            HStack(spacing: 12) {
                miniChip("Judge-Lane Rows: \(formattedInt(activeStats?.judgedRows))")
                miniChip("Threat Rows: \(formattedInt(activeStats?.threatRowsDetected))")
                miniChip("Threat Rate: \(formattedPercent(activeThreatRatePercent))")
                miniChip("Projected Threats: \(formattedInt(activeStats?.projectedThreatRows))")
            }

            if let warning = reviewInflationWarning {
                Text(warning)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(Color.orange.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 18))
            }
        }
        .padding(20)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 28))
    }

    private var intakeAndQueueRow: some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(alignment: .leading, spacing: 16) {
                Text("UPLOAD INTAKE")
                    .font(.headline)
                    .tracking(1.5)
                    .foregroundStyle(.teal)
                Text("Set the native inbox, processed, and failed folders for automatic workbook intake.")
                    .font(.title3)
                    .foregroundStyle(.secondary)

                VStack(alignment: .leading, spacing: 12) {
                    Text("Folder Setup")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("Dropped `.xlsx` files are picked up from the inbox folder, archived to processed on success, and moved to failed if intake cannot be completed.")
                        .foregroundStyle(.secondary)
                    VStack(alignment: .leading, spacing: 10) {
                        folderSelectorRow(
                            title: "Set Inbox Folder",
                            path: service.nativeConfig.intakeWatchDir,
                            chooseAction: service.chooseWatchFolder
                        )
                        folderSelectorRow(
                            title: "Set Processed Folder",
                            path: service.nativeConfig.intakeArchiveDir,
                            chooseAction: service.chooseProcessedFolder
                        )
                        folderSelectorRow(
                            title: "Set Failed Folder",
                            path: service.nativeConfig.intakeFailedDir,
                            chooseAction: service.chooseFailedFolder
                        )
                        Text(service.watchFolderStatus)
                            .foregroundStyle(.secondary)
                            .lineLimit(3)
                    }
                }
                .padding(18)
                .overlay(
                    RoundedRectangle(cornerRadius: 22)
                        .stroke(style: StrokeStyle(lineWidth: 1.2, dash: [5, 5]))
                        .foregroundStyle(.teal.opacity(0.45))
                )
            }
            .padding(20)
            .background(Color(NSColor.windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 28))
            .frame(maxWidth: .infinity, alignment: .leading)

            VStack(alignment: .leading, spacing: 16) {
                Text("INBOX ACTIVITY")
                    .font(.headline)
                    .tracking(1.5)
                    .foregroundStyle(.teal)
                if service.inboxActivities.isEmpty {
                    emptyCard("No inbox documents tracked yet.")
                } else {
                    ForEach(service.inboxActivities.prefix(4)) { activity in
                        inboxActivityCard(activity)
                    }
                }
            }
            .padding(20)
            .background(Color(NSColor.windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 28))
            .frame(maxWidth: 720, alignment: .leading)
        }
    }

    @ViewBuilder
    private func folderSelectorRow(title: String, path: String, chooseAction: @escaping () -> Void) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Button(title, action: chooseAction)
            Button(path) {
                service.openFolder(at: path)
            }
            .buttonStyle(.link)
            .lineLimit(1)
            .help(path)
        }
    }

    private var runsAndDetailRow: some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("RECENT RUNS")
                                .font(.headline)
                                .tracking(1.5)
                                .foregroundStyle(.teal)
                            Text("Persisted run records prioritized for operator decisions, not raw storage inspection.")
                                .font(.title3)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Refresh") { Task { await service.refreshRuntimeSnapshot() } }
                    }
                    if service.availableRuns.isEmpty {
                        emptyCard("No persisted run records discovered yet.")
                    } else {
                        ForEach(service.availableRuns.prefix(3)) { run in
                            runCard(run)
                        }
                    }
                }
                .padding(20)
                .background(Color(NSColor.windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 28))

                VStack(alignment: .leading, spacing: 16) {
                    Text("RUN DETAIL")
                        .font(.headline)
                        .tracking(1.5)
                        .foregroundStyle(.teal)
                    Text("Select a run to inspect state, review summary, and next operator actions.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                    if service.selectedRunID.isEmpty {
                        emptyCard("Choose a run from the left column to unlock lifecycle controls, review payloads, and action history.")
                    } else {
                        VStack(alignment: .leading, spacing: 12) {
                            summaryRow("Run ID", service.activeRunSummary.selectedRunID)
                            summaryRow("State", service.activeRunSummary.runState)
                            summaryRow("Review Summary", "\(service.pendingReviewCount) pending")
                            summaryRow("Upload Link", service.activeRunUploadID ?? "-")
                            if !service.activeRunSummary.nextActions.isEmpty {
                                Text("Next actions: \(service.activeRunSummary.nextActions.joined(separator: ", "))")
                                    .foregroundStyle(.secondary)
                            }
                            HStack(spacing: 12) {
                                Button("Refresh Run Detail") { Task { await service.selectRun(service.selectedRunID) } }
                                Button("Load Review Rows") { Task { await service.loadReviewQueueForSelectedRun() } }
                                Button("Open Review Queue") {
                                    service.navigate(to: .review)
                                }
                                Button("Open Operations") {
                                    service.navigate(to: .operations)
                                }
                            }
                            if !service.reviewPreviewRows.isEmpty {
                                Divider()
                                Text("Review Rows Preview")
                                    .font(.headline)
                                ForEach(service.reviewPreviewRows.prefix(3)) { row in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("Row \(row.rowIndex) · \(row.assignedCategory ?? "-")")
                                            .fontWeight(.semibold)
                                        Text(row.postText ?? "")
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                    .padding(.vertical, 4)
                                }
                            }
                        }
                    }
                }
                .padding(20)
                .background(Color(NSColor.windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 28))
            }
            .frame(maxWidth: .infinity)

            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("QUEUE OVERVIEW")
                        .font(.headline)
                        .tracking(1.5)
                        .foregroundStyle(.teal)
                    Text("High-level queue visibility stays in view; raw diagnostics are available only when needed.")
                        .font(.title3)
                        .foregroundStyle(.secondary)

                    LazyVGrid(columns: twoColumns, spacing: 14) {
                        metricCard("TRACKED UPLOADS", "\(service.operationsOverview?.uploads ?? 0)", "Indexed native upload records", icon: "tray.2", series: service.metricHistorySeries(.acceptedUploads), tint: .teal)
                        metricCard("ACTIVE UPLOADS", "\(service.operationsOverview?.activeUploads ?? 0)", "Currently running upload lanes", icon: "bolt.horizontal.circle", series: service.metricHistorySeries(.runRecords), tint: .orange)
                        metricCard("TOTAL SEGMENTS", "\(service.operationsOverview?.totalSegments ?? 0)", "Queued segment workload", icon: "square.grid.3x3.square", series: service.metricHistorySeries(.segmentQueue), tint: .purple)
                        metricCard("PROCESSED ROWS", "\(service.operationsOverview?.processedRows ?? 0)", "Rows completed across tracked uploads", icon: "checkmark.circle", series: service.metricHistorySeries(.processedRows), tint: .green)
                    }

                    HStack(spacing: 10) {
                        ForEach(queueStatusChips, id: \.self) { chip in
                            miniChip(chip)
                        }
                    }

                    DisclosureGroup("Raw Queue Diagnostics") {
                        Text(rawQueueDiagnostics)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                            .font(.system(.body, design: .monospaced))
                            .padding(.top, 8)
                    }
                }
                .padding(20)
                .background(Color(NSColor.windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 28))

                actionDock
            }
            .frame(maxWidth: 720)
        }
    }

    private var actionDock: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("ACTIONS")
                .font(.headline)
                .tracking(1.5)
                .foregroundStyle(.teal)
            HStack {
                Button("Refresh Runtime") { Task { await service.refreshRuntimeSnapshot() } }
                Button("Open Intake") {
                    service.navigate(to: .intake)
                }
                Button("Open Review") {
                    service.navigate(to: .review)
                }
                .disabled(service.selectedRunID.isEmpty)
                Button("Open Operations") {
                    service.navigate(to: .operations)
                }
                Button("Open Runs Directory") { service.openRunsDirectory() }
                Button("Open Logs") { service.openLogs() }
            }
        }
        .padding(20)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 28))
    }

    private var validationAndLogs: some View {
        VStack(alignment: .leading, spacing: 20) {
            GroupBox("Validation") {
                Text(service.preflightSummary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox("Logs") {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(service.logLines.enumerated()), id: \.offset) { _, line in
                            Text(line)
                                .font(.system(.caption, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(minHeight: 220)
            }
        }
    }

    private var uploadSummaries: [SpotUploadQueueSummary] {
        service.operationsOverview?.recentUploads.filter { ($0.status ?? "").lowercased() == "accepted" } ?? []
    }

    private var activeStats: SpotProcessingStats? { service.activeRunProcessingStats }

    private var activeProgressPercent: Double? {
        activeStats?.processedRows != nil && activeStats?.totalRows != nil
            ? percentage(processed: activeStats?.processedRows, total: activeStats?.totalRows)
            : service.activeRunProgressPercentage
    }

    private var activeRowsRemaining: Int? {
        guard let total = activeStats?.totalRows ?? service.activeRunTotalRows,
              let processed = activeStats?.processedRows ?? service.activeRunProcessedRows else { return nil }
        return max(total - processed, 0)
    }

    private var activeSegmentSubline: String? {
        guard let activeSegment = service.activeRunCurrentSegment else { return nil }
        let processed = max(activeSegment.processedRows ?? 0, 0)
        let total = max(activeSegment.rowCount ?? 0, 0)
        guard total > 0 else { return nil }
        let label = activeSegment.segmentIndex.map { "Current segment \($0)" } ?? "Current segment"
        return "\(label): \(processed)/\(total) rows"
    }

    private var processedRowsSubline: String {
        activeSegmentSubline ?? "Committed rows across completed segments"
    }

    private var rowProgressSubline: String {
        if let activeSegmentSubline {
            return "\(formattedETA(activeETASeconds)) · \(activeSegmentSubline)"
        }
        return formattedETA(activeETASeconds)
    }

    private var activeReviewRequiredRows: Int? {
        if let detected = activeStats?.reviewRequiredRowsDetected {
            return detected
        }
        return service.pendingReviewCount
    }

    private var reviewInflationWarning: String? {
        guard let processed = activeStats?.processedRows, processed > 0 else { return nil }
        guard let reviewRequired = activeStats?.reviewRequiredRowsDetected, reviewRequired >= processed else { return nil }
        let failureFlags = Set(
            service.reviewPreviewRows
                .flatMap { $0.flags ?? [] }
        )
        let infrastructureFailureFlags: Set<String> = [
            "MODEL_REQUEST_FAILED",
            "CLASSIFIER_FALLBACK_FAILED",
            "DRAFTER_UNAVAILABLE",
            "JUDGE_UNAVAILABLE",
            "SECOND_PASS_UNAVAILABLE",
        ]
        guard !failureFlags.isDisjoint(with: infrastructureFailureFlags) else { return nil }
        return "Review-required count is currently failure-driven. The classifier lane is falling back or timing out, so processed rows are being routed to human review by infrastructure policy."
    }

    private var activeETASeconds: Int? {
        if let summary = uploadSummaries.first(where: { ($0.run?.runID ?? "") == service.selectedRunID }) {
            return summary.estimatedRemainingSeconds
        }
        guard let remaining = activeRowsRemaining,
              let avg = activeStats?.avgSecondsPerRow else { return nil }
        return Int(Double(remaining) * avg)
    }

    private var activeThreatRatePercent: Double? {
        guard let rate = activeStats?.threatRate else { return nil }
        return rate * 100
    }

    private var acceptedUploadCount: String {
        "\(max(uploadSummaries.count, service.availableUploads.count))"
    }

    private var overviewSegmentCount: String {
        "\(service.operationsOverview?.totalSegments ?? 0)"
    }

    private var overviewSegmentHealth: String {
        guard let overview = service.operationsOverview else { return "No queued uploads" }
        let statuses = overview.segmentsByStatus
        let completed = statuses["COMPLETED"] ?? 0
        let processing = statuses["PROCESSING"] ?? 0
        let queued = statuses["QUEUED"] ?? 0
        return "\(completed) completed · \(processing) processing · \(queued) queued"
    }

    private var overviewNarrative: String {
        guard let active = uploadSummaries.first(where: {
            let state = ($0.run?.state ?? "").uppercased()
            return ["STARTING", "PROCESSING", "PAUSED", "QUEUED"].contains(state)
        }) else {
            return "Queue summary unavailable."
        }
        return "Active intake \(active.filename ?? active.uploadID) is in \((active.run?.state ?? active.status ?? "unknown").lowercased()) state with \(formattedPercent(active.rowProgressPercentage)) row completion and \(formattedPercent(active.segmentProgressPercentage)) segment completion."
    }

    private var queueStatusChips: [String] {
        guard let overview = service.operationsOverview else { return [] }
        return overview.segmentsByStatus
            .filter { $0.value > 0 }
            .map { "\($0.key) \($0.value)" }
            .sorted()
    }

    private var rawQueueDiagnostics: String {
        guard let overview = service.operationsOverview else { return "No queue data loaded yet." }
        let uploads = overview.recentUploads.prefix(5).map { summary in
            "\(summary.filename ?? summary.uploadID) · row \(formattedPercent(summary.rowProgressPercentage)) · segment \(formattedPercent(summary.segmentProgressPercentage))"
        }.joined(separator: "\n")
        return """
        uploads=\(overview.uploads)
        active_uploads=\(overview.activeUploads)
        total_segments=\(overview.totalSegments)
        processed_rows=\(overview.processedRows)

        \(uploads)
        """
    }

    private var stateStackValue: String {
        if service.activeRunSummary.selectedRunID.isEmpty { return "-" }
        return service.activeRunSummary.runState
    }

    private var stateStackSubline: String {
        if service.activeRunSummary.selectedRunID.isEmpty { return "No active run" }
        return service.activeRunSummary.selectedRunID
    }

    private var compactRuntimeTitle: String {
        if service.activeRunSummary.selectedRunID.isEmpty {
            return "No active run"
        }
        return "\(service.activeRunSummary.runState) · \(service.activeRunSummary.selectedRunID)"
    }

    private var compactRuntimeDetail: String {
        if let progress = activeProgressPercent {
            return "\(formattedPercent(progress)) · \(formattedInt(activeStats?.processedRows ?? service.activeRunProcessedRows)) rows"
        }
        return "Live run strip collapsed"
    }

    private var compactRuntimeTint: Color {
        stateTint(service.activeRunSummary.runState)
    }

    private var avgSecondsTint: Color {
        deviationTint(
            current: activeStats?.avgSecondsPerRow,
            baseline: service.historicalBaseline.avgSecondsPerRow
        )
    }

    private var reviewRateTint: Color {
        deviationTint(
            current: service.activeReviewRequiredRate,
            baseline: service.historicalBaseline.reviewRequiredRate
        )
    }

    private var avgSecondsDeltaText: String {
        deltaText(
            current: activeStats?.avgSecondsPerRow,
            baseline: service.historicalBaseline.avgSecondsPerRow
        )
    }

    private var reviewRateDeltaText: String {
        deltaText(
            current: service.activeReviewRequiredRate,
            baseline: service.historicalBaseline.reviewRequiredRate,
            suffix: "review rate vs all-time avg"
        )
    }

    private var twoColumns: [GridItem] {
        Array(repeating: GridItem(.flexible(minimum: 160), spacing: 14), count: 2)
    }

    @ViewBuilder
    private func metricCard(_ label: String, _ value: String, _ sub: String, icon: String, series: [Double], tint: Color = .primary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                Image(systemName: icon)
                    .font(.headline)
                    .foregroundStyle(tint)
                    .frame(width: 34, height: 34)
                    .background(tint.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                Spacer()
                Text(label)
                    .font(.headline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.trailing)
            }

            Spacer(minLength: 2)

            Text(value)
                .font(.system(size: 30, weight: .bold, design: .default))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.7)

            if !sub.isEmpty {
                Text(sub)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.8)
            }

            Spacer(minLength: 4)

            SpotMetricSparklineView(values: series, color: tint)
                .frame(height: 56)
                .padding(.top, 6)
            if let last = series.last, let first = series.dropLast().last {
                Text(trendText(last: last, previous: first))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            } else {
                Text("History building")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 210, alignment: .leading)
        .padding(18)
        .background(
            LinearGradient(
                colors: [
                    Color(NSColor.controlBackgroundColor),
                    Color(NSColor.controlBackgroundColor).opacity(0.92)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 24)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    private func stateTint(_ state: String) -> Color {
        switch state.uppercased() {
        case "PROCESSING", "STARTING", "WRITING":
            return .teal
        case "PAUSED":
            return .yellow
        case "FAILED", "CANCELLED":
            return .orange
        case "COMPLETED":
            return .green
        default:
            return .primary
        }
    }

    private func deviationTint(current: Double?, baseline: Double?) -> Color {
        guard let current, let baseline, baseline > 0 else { return .primary }
        let ratio = (current - baseline) / baseline
        if ratio > 0.05 { return .orange }
        if ratio < -0.05 { return .teal }
        return .primary
    }

    private func deltaText(current: Double?, baseline: Double?, suffix: String = "vs all-time avg") -> String {
        guard let current, let baseline, baseline > 0 else { return "All-time avg unavailable" }
        let delta = ((current - baseline) / baseline) * 100
        let sign = delta > 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", delta))% \(suffix)"
    }

    private func trendText(last: Double, previous: Double) -> String {
        guard previous != 0 else { return "Trend stabilizing" }
        let delta = ((last - previous) / abs(previous)) * 100
        let sign = delta > 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", delta))% vs previous snapshot"
    }

    private func runSeries(from run: SpotRunRecord, kind: SpotMetricHistoryKind) -> [Double] {
        switch kind {
        case .processedRows:
            if let processed = run.processingStats?.processedRows ?? run.progress?.processedRows,
               let total = run.processingStats?.totalRows ?? run.progress?.totalRows {
                return [0, Double(processed), Double(total)]
            }
            if let processed = run.processingStats?.processedRows ?? run.progress?.processedRows {
                return [Double(processed)]
            }
        case .reviewRequiredRows:
            if let pending = run.reviewSummary?.pendingRows {
                return [Double(pending)]
            }
        default:
            break
        }
        return []
    }

    @ViewBuilder
    private func emptyCard(_ message: String) -> some View {
        Text(message)
            .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
            .padding(18)
            .background(Color(NSColor.controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 22))
            .foregroundStyle(.secondary)
    }

    @ViewBuilder
    private func miniChip(_ text: String) -> some View {
        Text(text)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color(NSColor.controlBackgroundColor))
            .clipShape(Capsule())
    }

    @ViewBuilder
    private func summaryRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(label)
                .foregroundStyle(.secondary)
                .frame(width: 120, alignment: .leading)
            Text(value)
                .textSelection(.enabled)
        }
    }

    @ViewBuilder
    private func runCard(_ run: SpotRunRecord) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(run.runID)
                        .font(.title3)
                        .fontWeight(.semibold)
                    Text("Language: \(run.language ?? "-") · Review mode: \(run.reviewMode ?? "-")")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                miniChip(run.state ?? "UNKNOWN")
            }

            HStack(spacing: 12) {
                metricCard("ROWS", "\(run.progress?.processedRows ?? 0) / \(run.progress?.totalRows ?? 0)", "Processed vs accepted rows", icon: "list.number", series: runSeries(from: run, kind: .processedRows), tint: .teal)
                metricCard("REVIEW QUEUE", "\(run.reviewSummary?.pendingRows ?? 0)", "Rows awaiting reviewer action", icon: "exclamationmark.bubble", series: runSeries(from: run, kind: .reviewRequiredRows), tint: .orange)
            }

            Text("Upload link: \(run.runID == service.selectedRunID ? (service.activeRunUploadID ?? "-") : "-")")
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                Button("Open Run Detail") { Task { await service.selectRun(run.runID) } }
                Button("Full Page") {
                    Task { await service.selectRun(run.runID) }
                    service.navigate(to: .operations)
                }
                Button("Review Queue") {
                    Task { await service.selectRun(run.runID) }
                    service.navigate(to: .review)
                }
            }
        }
        .padding(18)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    @ViewBuilder
    private func uploadCard(_ summary: SpotUploadQueueSummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(summary.filename ?? summary.uploadID)
                        .font(.title3)
                        .fontWeight(.semibold)
                    Text(summary.uploadID)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                miniChip(summary.status ?? "unknown")
            }

            HStack(spacing: 12) {
                metricCard("ROWS", formattedInt(summary.rowCount), "Rows discovered in workbook", icon: "text.line.first.and.arrowtriangle.forward", series: [Double(summary.rowCount ?? 0)], tint: .teal)
                metricCard("SEGMENTS", formattedInt(summary.segmentCount), "Queued segment batches", icon: "square.3.layers.3d.top.filled", series: [Double(summary.segmentCount ?? 0)], tint: .purple)
            }

            Text("Row progress \(formattedPercent(summary.rowProgressPercentage)) · Segment progress \(formattedPercent(summary.segmentProgressPercentage))")
                .foregroundStyle(.secondary)

            HStack(spacing: 10) {
                ForEach(segmentChips(for: summary), id: \.self) { chip in
                    miniChip(chip)
                }
            }

            Button("Use For Run Start") {
                service.useUploadForRunStart(summary.uploadID)
            }
        }
        .padding(18)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    @ViewBuilder
    private func inboxActivityCard(_ activity: SpotInboxDocumentActivity) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(activity.filename)
                        .font(.title3)
                        .fontWeight(.semibold)
                    Text(activity.stage.replacingOccurrences(of: "_", with: " "))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                miniChip(relativeTimestamp(activity.updatedAt))
            }

            Text(activity.note)
                .foregroundStyle(.secondary)

            if let uploadID = activity.uploadID, !uploadID.isEmpty {
                Text("Upload: \(uploadID)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            if let runID = activity.runID, !runID.isEmpty {
                Text("Run: \(runID)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            if let destinationPath = activity.destinationPath, !destinationPath.isEmpty {
                Text("Destination: \(destinationPath)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .textSelection(.enabled)
            }

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Text("History")
                    .font(.headline)
                ForEach(activity.events.suffix(6).reversed()) { event in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(event.stage.replacingOccurrences(of: "_", with: " "))
                                .font(.caption)
                                .fontWeight(.semibold)
                            Spacer()
                            Text(relativeTimestamp(event.createdAt))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Text(event.note)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if let uploadID = event.uploadID, !uploadID.isEmpty {
                            Text("upload \(uploadID)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                        if let runID = event.runID, !runID.isEmpty {
                            Text("run \(runID)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .padding(18)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    private func segmentChips(for summary: SpotUploadQueueSummary) -> [String] {
        (summary.segmentsByStatus ?? [:])
            .filter { $0.value > 0 }
            .map { "\($0.key) \($0.value)" }
            .sorted()
    }

    private func formattedInt(_ value: Int?) -> String {
        guard let value else { return "-" }
        return "\(value)"
    }

    private func formattedPercent(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "%.2f%%", value)
    }

    private func formattedDecimal(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "%.2f s", value)
    }

    private func formattedDuration(_ seconds: Int?) -> String {
        guard let seconds else { return "-" }
        if seconds < 60 { return "\(seconds)s" }
        let minutes = seconds / 60
        let remaining = seconds % 60
        if minutes < 60 { return "\(minutes)m \(remaining)s" }
        let hours = minutes / 60
        let remainingMinutes = minutes % 60
        return "\(hours)h \(remainingMinutes)m"
    }

    private func formattedETA(_ seconds: Int?) -> String {
        guard let seconds, seconds > 0 else { return "Estimated time remaining unavailable" }
        return "ETA \(formattedDuration(seconds))"
    }

    private func relativeTimestamp(_ secondsSince1970: TimeInterval) -> String {
        let delta = max(Int(Date().timeIntervalSince1970 - secondsSince1970), 0)
        if delta < 60 { return "\(delta)s ago" }
        if delta < 3600 { return "\(delta / 60)m ago" }
        if delta < 86400 { return "\(delta / 3600)h ago" }
        return "\(delta / 86400)d ago"
    }

    private func percentage(processed: Int?, total: Int?) -> Double? {
        guard let processed, let total, total > 0 else { return nil }
        return (Double(processed) / Double(total)) * 100
    }
}
