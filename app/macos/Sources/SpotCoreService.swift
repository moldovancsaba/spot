import AppKit
import Foundation
import SQLite3

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

@MainActor
final class SpotCoreService: ObservableObject {
    private struct WatchedFileSnapshot {
        let size: UInt64
        let modifiedAt: Date
        let stablePasses: Int
    }

    private struct RunHealthObservation {
        let processedRows: Int
        let observedAt: Date
        let statsUpdatedAt: Date?
    }

    private enum AutomaticRunHealingAction {
        case recover(runID: String, reason: String)
        case heal(runID: String, reason: String)
    }

    @Published var runtimeState: SpotRuntimeState = .offline
    @Published var currentPage: SpotAppPage = .dashboard
    @Published var baseURL: URL?
    @Published var lastRefreshAt: Date?
    @Published var launchErrorMessage: String = ""
    @Published var preflightSummary: String = "Preflight has not run yet."
    @Published var authSummary: String = "Native local mode."
    @Published var authEnabledForNativeApp: Bool = false
    @Published var operatorActorName: String = "local-operator"
    @Published var operatorRole: String = "operator"
    @Published var operatorAccessCode: String = "spot-local"
    @Published var selectedRunID: String = ""
    @Published var activeRunSummary: SpotRuntimeSummary = .empty
    @Published var pendingReviewCount: Int = 0
    @Published var availableRuns: [SpotRunRecord] = []
    @Published var reviewPreviewRows: [SpotReviewRowPreview] = []
    @Published var reviewQueueRows: [SpotReviewRowPreview] = []
    @Published var selectedReviewRowIndex: Int?
    @Published var activeReviewInspector: SpotReviewRowInspector?
    @Published var reviewDraft: SpotReviewDraft = .empty
    @Published var reviewSaveMessage: String = ""
    @Published var availableUploads: [SpotUploadRecord] = []
    @Published var operationsOverview: SpotOperationsOverview?
    @Published var selectedUploadID: String = ""
    @Published var uploadMessage: String = ""
    @Published var newRunID: String = ""
    @Published var startLanguage: String = "de"
    @Published var startReviewMode: String = "partial"
    @Published var startLimit: String = ""
    @Published var activeArtifacts: [SpotArtifactItem] = []
    @Published var artifactMessage: String = ""
    @Published var signoffDecision: String = "accepted"
    @Published var signoffNote: String = ""
    @Published var logLines: [String] = []
    @Published var nativeConfig: SpotNativeConfig = .empty
    @Published var watchFolderStatus: String = "Watch folder is not configured."
    @Published var inboxActivities: [SpotInboxDocumentActivity] = []

    private var launchProcess: Process?
    private var refreshTask: Task<Void, Never>?
    private let preferredHost = "127.0.0.1"
    private let session: URLSession
    private var latestRunDetail: SpotRunDetail?
    private var watchedFileSnapshots: [String: WatchedFileSnapshot] = [:]
    private var watchFolderInFlight: Set<String> = []
    private var lastAutoLaunchAttemptAt: Date?
    private var autoRecoveryAttemptedRunIDs: [String: Date] = [:]
    private var autoHealingAttemptedRunIDs: [String: Date] = [:]
    private var runHealthObservations: [String: RunHealthObservation] = [:]
    private var runtimeAutoRecoveryEnabled = true
    private var didBootstrapRuntime = false
    private var automaticHealingInFlight = false

    init() {
        let configuration = URLSessionConfiguration.default
        configuration.httpCookieStorage = HTTPCookieStorage.shared
        configuration.httpShouldSetCookies = true
        configuration.waitsForConnectivity = false
        configuration.timeoutIntervalForRequest = 15
        configuration.timeoutIntervalForResource = 45
        self.session = URLSession(configuration: configuration)
        ensureSupportDirectories()
        ensureNativeConfigFile()
        let loadedConfig = loadNativeConfig()
        nativeConfig = loadedConfig
        inboxActivities = loadInboxActivities()
        if nativeConfig.runsDir.isEmpty {
            nativeConfig.runsDir = spotDataHome.appending(path: "runs").path
        }
        if nativeConfig.logsDir.isEmpty {
            nativeConfig.logsDir = spotLogHome.path
        }
        if nativeConfig.lockedSSOTPath.isEmpty {
            nativeConfig.lockedSSOTPath = bundledCoreRootURL()?.appending(path: "ssot/ssot.json").path ?? ""
        }
        if nativeConfig.intakeWatchDir.isEmpty {
            nativeConfig.intakeWatchDir = defaultIntakeInboxURL.path
        }
        if nativeConfig.intakeArchiveDir.isEmpty {
            nativeConfig.intakeArchiveDir = defaultIntakeProcessedURL.path
        }
        if nativeConfig.intakeFailedDir.isEmpty {
            nativeConfig.intakeFailedDir = defaultIntakeFailedURL.path
        }
        if newRunID.isEmpty {
            newRunID = suggestedRunID()
        }
        saveNativeConfig()
        refreshWatchFolderStatus()
    }

    deinit {
        refreshTask?.cancel()
    }

    func startMonitoring() {
        guard refreshTask == nil else { return }
        refreshTask = Task {
            while !Task.isCancelled {
                await refreshHealth()
                await processWatchedIntakeDirectory()
                await selfHealRuntimeIfNeeded()
                try? await Task.sleep(for: .seconds(5))
            }
        }
    }

    func bootstrapNativeRuntimeIfNeeded() async {
        guard !didBootstrapRuntime else { return }
        didBootstrapRuntime = true
        appendSupervisorLog("bootstrapNativeRuntimeIfNeeded started")
        await validatePreflightSecurity()
        launchSpot()
        await waitForRuntimeReadyAfterLaunch()
    }

    func refreshHealth() async {
        guard let reachable = await detectReachableRuntime() else {
            if case .starting = runtimeState {
                lastRefreshAt = Date()
            } else if launchProcess?.isRunning == true {
                runtimeState = .starting
                lastRefreshAt = Date()
            } else {
                runtimeState = .offline
                attemptAutomaticRuntimeRecoveryIfNeeded()
            }
            return
        }
        baseURL = reachable.0
        let payload = reachable.1
        runtimeState = .online
        lastRefreshAt = Date()
        launchErrorMessage = ""
        preflightSummary = "Runtime reachable. Status: \(payload.status). Version: \(payload.version)."
        let rootURL = reachable.0
        activeRunSummary.healthDescription = "Health endpoint reports launch.ready=\(payload.launch.ready)"
        do {
            try await refreshAuthenticatedSnapshot(rootURL: rootURL)
            lastAutoLaunchAttemptAt = nil
        } catch {
            authSummary = "Runtime sync failed: \(error.localizedDescription)"
            launchErrorMessage = authSummary
        }
    }

    func runPreflight() async {
        do {
            try validateLaunchConfiguration()
            let pythonPath = nativeConfig.pythonBin.trimmingCharacters(in: .whitespacesAndNewlines)
            let ssotPath = try resolveLockedSSOTPath()
            let process = Process()
            let pipe = Pipe()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = [
                "-lc",
                "\"\(pythonPath)\" -m src.cli preflight --ssot \"\(ssotPath)\" --runs-dir \"\(nativeConfig.runsDir)\" --port \"\(nativeConfig.port)\"",
            ]
            process.currentDirectoryURL = bundledCoreRootURL()
            process.environment = launchEnvironment()
            process.standardOutput = pipe
            process.standardError = pipe
            try process.run()
            process.waitUntilExit()
            let output = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            preflightSummary = output.isEmpty ? "Preflight completed." : output.trimmingCharacters(in: .whitespacesAndNewlines)
        } catch {
            preflightSummary = error.localizedDescription
        }
    }

    func launchSpot() {
        guard launchProcess == nil || launchProcess?.isRunning == false else { return }
        do {
            try validateLaunchConfiguration()
            guard let launcher = resolveBundledLauncher() else {
                runtimeState = .error("Bundled launcher is missing.")
                appendSupervisorLog("launchSpot failed: bundled launcher path could not be resolved")
                return
            }
            runtimeAutoRecoveryEnabled = true
            runtimeState = .starting
            launchErrorMessage = "Starting local runtime..."
            appendSupervisorLog("launchSpot starting with launcher \(launcher.path)")

            let process = Process()
            let pipe = Pipe()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = [launcher.path]
            process.environment = launchEnvironment()
            process.standardOutput = pipe
            process.standardError = pipe

            pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
                let data = handle.availableData
                guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
                Task { @MainActor in
                    self?.appendLog(text)
                }
            }

            process.terminationHandler = { [weak self] proc in
                Task { @MainActor in
                    self?.launchProcess = nil
                    self?.appendSupervisorLog("runtime child exited with code \(proc.terminationStatus)")
                    if proc.terminationStatus != 0 {
                        self?.runtimeState = .error("Bundled runtime exited with code \(proc.terminationStatus).")
                        self?.launchErrorMessage = "Bundled runtime exited with code \(proc.terminationStatus)."
                    } else if case .online = self?.runtimeState {
                        self?.runtimeState = .offline
                    }
                }
            }

            try process.run()
            launchProcess = process
            appendSupervisorLog("launchSpot spawned runtime pid \(process.processIdentifier)")
        } catch {
            runtimeState = .error(error.localizedDescription)
            launchErrorMessage = error.localizedDescription
            appendSupervisorLog("launchSpot failed: \(error.localizedDescription)")
        }
    }

    func restartSpot() {
        Task {
            runtimeAutoRecoveryEnabled = true
            await gracefulStopRuntime(suspendActiveRuns: true)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                self.launchSpot()
            }
        }
    }

    func stopSpot() {
        Task {
            runtimeAutoRecoveryEnabled = false
            await gracefulStopRuntime(suspendActiveRuns: true)
        }
    }

    func prepareForApplicationTermination() {
        refreshTask?.cancel()
        refreshTask = nil
        runtimeAutoRecoveryEnabled = false
        let semaphore = DispatchSemaphore(value: 0)
        Task { @MainActor in
            await gracefulStopRuntime(suspendActiveRuns: true)
            semaphore.signal()
        }
        _ = semaphore.wait(timeout: .now() + 8)
    }

    func openLogs() {
        NSWorkspace.shared.open(spotLogHome)
    }

    func openNativeConfig() {
        let url = nativeConfigURL
        if !FileManager.default.fileExists(atPath: url.path) {
            ensureNativeConfigFile()
        }
        NSWorkspace.shared.open(url)
    }

    func chooseWatchFolder() {
        chooseDirectory(
            title: "Choose Inbox Folder",
            message: "Choose the folder that {spot} should watch for incoming .xlsx workbooks."
        ) { url in
            nativeConfig.intakeWatchDir = url.path
        }
    }

    func chooseProcessedFolder() {
        chooseDirectory(
            title: "Choose Processed Folder",
            message: "Choose the folder where {spot} should move successfully queued workbooks."
        ) { url in
            nativeConfig.intakeArchiveDir = url.path
        }
    }

    func chooseFailedFolder() {
        chooseDirectory(
            title: "Choose Failed Folder",
            message: "Choose the folder where {spot} should move failed intake workbooks."
        ) { url in
            nativeConfig.intakeFailedDir = url.path
        }
    }

    func openWatchFolder() {
        let url = URL(fileURLWithPath: nativeConfig.intakeWatchDir)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(url)
    }

    func openProcessedIntakeFolder() {
        let url = URL(fileURLWithPath: nativeConfig.intakeArchiveDir)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(url)
    }

    func openFailedIntakeFolder() {
        let url = URL(fileURLWithPath: nativeConfig.intakeFailedDir)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(url)
    }

    func openFolder(at path: String) {
        let trimmed = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let url = URL(fileURLWithPath: trimmed)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(url)
    }

    func setAutoStartWatchFolder(_ enabled: Bool) {
        nativeConfig.autoStartWatchFolder = enabled
        saveNativeConfig()
        refreshWatchFolderStatus()
    }

    func reloadNativeConfig() {
        nativeConfig = loadNativeConfig()
        if nativeConfig.runsDir.isEmpty {
            nativeConfig.runsDir = spotDataHome.appending(path: "runs").path
        }
        if nativeConfig.logsDir.isEmpty {
            nativeConfig.logsDir = spotLogHome.path
        }
        if nativeConfig.lockedSSOTPath.isEmpty {
            nativeConfig.lockedSSOTPath = bundledCoreRootURL()?.appending(path: "ssot/ssot.json").path ?? ""
        }
        if nativeConfig.intakeWatchDir.isEmpty {
            nativeConfig.intakeWatchDir = defaultIntakeInboxURL.path
        }
        if nativeConfig.intakeArchiveDir.isEmpty {
            nativeConfig.intakeArchiveDir = defaultIntakeProcessedURL.path
        }
        if nativeConfig.intakeFailedDir.isEmpty {
            nativeConfig.intakeFailedDir = defaultIntakeFailedURL.path
        }
        refreshWatchFolderStatus()
    }

    func rewriteNativeConfigTemplate() {
        ensureNativeConfigFile(forceRewrite: true)
        reloadNativeConfig()
        preflightSummary = "Native runtime config template was refreshed at \(nativeConfigURL.path)."
    }

    func openRunsDirectory() {
        NSWorkspace.shared.open(URL(fileURLWithPath: nativeConfig.runsDir))
    }

    func openArtifactsDirectory(runID: String) {
        guard !runID.isEmpty else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: nativeConfig.runsDir).appending(path: runID))
    }

    func refreshRuntimeSnapshot() async {
        await refreshHealth()
    }

    func navigate(to page: SpotAppPage) {
        currentPage = page
    }

    func loginCurrentOperatorSession() async {
        guard authEnabledForNativeApp else {
            authSummary = "Native local mode · authentication disabled."
            return
        }
        guard let baseURL else {
            authSummary = "Runtime is not reachable yet."
            return
        }
        do {
            let auth = try await loginAsRole(
                baseURL: baseURL,
                role: operatorRole.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "operator" : operatorRole,
                actorName: operatorActorName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "local-operator" : operatorActorName
            )
            if let session = auth.session {
                authSummary = "Authenticated as \(session.actorName) · role \(session.role) · local auth enabled."
            }
            await refreshHealth()
        } catch {
            authSummary = "Login failed: \(error.localizedDescription)"
        }
    }

    func logoutCurrentOperatorSession() async {
        guard authEnabledForNativeApp else {
            authSummary = "Native local mode · authentication disabled."
            return
        }
        guard let baseURL else { return }
        do {
            var request = URLRequest(url: baseURL.appending(path: "auth/logout"))
            request.httpMethod = "POST"
            let _: SpotAuthSessionResponse = try await requestJSON(request: request)
            authSummary = "Logged out."
            await refreshHealth()
        } catch {
            authSummary = "Logout failed: \(error.localizedDescription)"
        }
    }

    func pickAndIntakeWorkbook() async {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Intake Workbook"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        await intakeWorkbook(fileURL: url)
    }

    func intakeWorkbook(fileURL: URL) async {
        do {
            let record = try await performWorkbookIntake(fileURL: fileURL)
            uploadMessage = "Intake finished for \(record.filename ?? record.uploadID). Status: \(record.status ?? "unknown")."
            await refreshUploads()
        } catch {
            uploadMessage = "Workbook intake failed: \(error.localizedDescription)"
        }
    }

    func refreshUploads() async {
        guard let baseURL else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            let uploads: [SpotUploadRecord] = try await requestJSON(url: baseURL.appending(path: "uploads"))
            availableUploads = uploads
            if selectedUploadID.isEmpty, let firstAccepted = uploads.first(where: { ($0.status ?? "").lowercased() == "accepted" }) {
                selectedUploadID = firstAccepted.uploadID
            }
        } catch {
            uploadMessage = "Could not refresh uploads: \(error.localizedDescription)"
        }
    }

    func refreshOperationsOverview() async {
        guard let baseURL else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            let overview: SpotOperationsOverview = try await requestJSON(url: baseURL.appending(path: "operations/overview"))
            operationsOverview = overview
        } catch {
            artifactMessage = "Could not refresh operations overview: \(error.localizedDescription)"
        }
    }

    func startRunFromSelectedUpload() async {
        guard let baseURL else {
            uploadMessage = "Runtime is not reachable yet."
            return
        }
        let runID = newRunID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !runID.isEmpty else {
            uploadMessage = "Provide a run ID before starting."
            return
        }
        guard !selectedUploadID.isEmpty else {
            uploadMessage = "Select an accepted intake record first."
            return
        }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            var payload: [String: Any] = [
                "upload_id": selectedUploadID,
                "language": startLanguage,
                "review_mode": startReviewMode,
            ]
            if let limit = Int(startLimit.trimmingCharacters(in: .whitespacesAndNewlines)), limit > 0 {
                payload["limit"] = limit
            }
            var request = URLRequest(url: baseURL.appending(path: "classify/start/\(runID)"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])
            let _: SpotRunStartResponse = try await requestJSON(request: request)
            uploadMessage = "Run \(runID) started from intake record \(selectedUploadID)."
            newRunID = suggestedRunID()
            await refreshHealth()
            await refreshUploads()
            await refreshOperationsOverview()
        } catch {
            uploadMessage = "Could not start run: \(error.localizedDescription)"
        }
    }

    func triggerWatchedFolderScan() async {
        await processWatchedIntakeDirectory(forceScan: true)
    }

    func selectRun(_ runID: String) async {
        guard !runID.isEmpty else { return }
        selectedRunID = runID
        guard let baseURL else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            do {
                let detail: SpotRunDetail = try await requestJSON(url: baseURL.appending(path: "runs/\(runID)/detail"))
                applyRunDetail(detail)
                try await loadReviewQueue(for: runID)
            } catch {
                try await applyLightweightRunStatus(baseURL: baseURL, runID: runID)
                reviewSaveMessage = "Loaded lightweight run status while full detail is unavailable."
            }
        } catch {
            authSummary = "Could not load run \(runID): \(error.localizedDescription)"
        }
    }

    func loadReviewQueueForSelectedRun() async {
        guard !selectedRunID.isEmpty else { return }
        do {
            try await loadReviewQueue(for: selectedRunID)
        } catch {
            reviewSaveMessage = "Could not load review queue: \(error.localizedDescription)"
        }
    }

    func loadReviewInspector(rowIndex: Int) async {
        guard let baseURL, !selectedRunID.isEmpty else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            let inspector: SpotReviewRowInspector = try await requestJSON(
                url: baseURL.appending(path: "runs/\(selectedRunID)/review-rows/\(rowIndex)")
            )
            selectedReviewRowIndex = rowIndex
            activeReviewInspector = inspector
            reviewDraft = SpotReviewDraft(
                reviewState: inspector.reviewControls.reviewState,
                reviewDecision: inspector.reviewControls.reviewDecision ?? "",
                reviewerNote: inspector.reviewControls.reviewerNote
            )
            reviewSaveMessage = ""
        } catch {
            reviewSaveMessage = "Could not load review row \(rowIndex): \(error.localizedDescription)"
        }
    }

    func saveActiveReview() async {
        guard let baseURL, !selectedRunID.isEmpty, let rowIndex = selectedReviewRowIndex else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            var request = URLRequest(url: baseURL.appending(path: "runs/\(selectedRunID)/review-rows/\(rowIndex)"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let payload: [String: Any] = [
                "review_state": reviewDraft.reviewState,
                "review_decision": reviewDraft.reviewDecision.isEmpty ? NSNull() : reviewDraft.reviewDecision,
                "reviewer_note": reviewDraft.reviewerNote,
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])
            let updated: SpotReviewRowPreview = try await requestJSON(request: request)
            mergeUpdatedReviewRow(updated)
            reviewSaveMessage = "Saved row \(rowIndex) review state."
            try await loadReviewQueue(for: selectedRunID)
            await loadReviewInspector(rowIndex: rowIndex)
            await refreshHealth()
        } catch {
            reviewSaveMessage = "Could not save review row: \(error.localizedDescription)"
        }
    }

    func performRunOperation(_ operation: String) async {
        guard let baseURL, !selectedRunID.isEmpty else { return }
        let path: String
        switch operation {
        case "pause":
            path = "classify/pause/\(selectedRunID)"
        case "resume":
            path = "classify/resume/\(selectedRunID)"
        case "cancel":
            path = "runs/\(selectedRunID)/cancel"
        case "retry":
            path = "runs/\(selectedRunID)/retry"
        case "recover":
            path = "runs/\(selectedRunID)/recover"
        case "heal":
            path = "runs/\(selectedRunID)/heal"
        default:
            return
        }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            var request = URLRequest(url: baseURL.appending(path: path))
            request.httpMethod = "POST"
            let _: SpotOperationResponse = try await requestJSON(request: request)
            artifactMessage = "Run operation '\(operation)' submitted for \(selectedRunID)."
            await refreshHealth()
            await refreshOperationsOverview()
        } catch {
            artifactMessage = "Run operation failed: \(error.localizedDescription)"
        }
    }

    func loadArtifactsForSelectedRun() async {
        guard let baseURL, !selectedRunID.isEmpty else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            let center: SpotArtifactCenter = try await requestJSON(url: baseURL.appending(path: "runs/\(selectedRunID)/artifacts"))
            activeArtifacts = center.artifacts
            signoffDecision = center.signoff?.decision ?? "accepted"
            signoffNote = center.signoff?.note ?? ""
            artifactMessage = "Loaded \(center.artifacts.count) artifact(s) for \(selectedRunID)."
        } catch {
            artifactMessage = "Could not load artifacts: \(error.localizedDescription)"
        }
    }

    func submitSignoff() async {
        guard let baseURL, !selectedRunID.isEmpty else { return }
        do {
            _ = try await loginAsRole(baseURL: baseURL, role: "admin", actorName: "spot-native-admin")
            var request = URLRequest(url: baseURL.appending(path: "runs/\(selectedRunID)/signoff"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let payload: [String: Any] = [
                "decision": signoffDecision,
                "note": signoffNote,
            ]
            request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])
            let _: SpotSignoffRecord = try await requestJSON(request: request)
            artifactMessage = "Run \(selectedRunID) signed off with decision '\(signoffDecision)'."
            await refreshHealth()
            await loadArtifactsForSelectedRun()
        } catch {
            artifactMessage = "Could not sign off run: \(error.localizedDescription)"
        }
    }

    func openArtifact(_ artifact: SpotArtifactItem) {
        NSWorkspace.shared.open(URL(fileURLWithPath: artifact.path))
    }

    func useUploadForRunStart(_ uploadID: String) {
        selectedUploadID = uploadID
        uploadMessage = "Selected intake record \(uploadID) for run start."
    }

    func validatePreflightSecurity() async {
        do {
            try validateLaunchConfiguration()
            preflightSummary = "Launch configuration passed native security checks."
        } catch {
            preflightSummary = error.localizedDescription
        }
    }

    func validateLaunchConfiguration() throws {
        guard let launcher = resolveBundledLauncher(), FileManager.default.isExecutableFile(atPath: launcher.path) else {
            throw NSError(domain: "SpotCoreService", code: 1, userInfo: [NSLocalizedDescriptionKey: "Bundled launcher is missing or not executable."])
        }
        let pythonPath = nativeConfig.pythonBin.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pythonPath.isEmpty, FileManager.default.isExecutableFile(atPath: pythonPath) else {
            throw NSError(domain: "SpotCoreService", code: 2, userInfo: [NSLocalizedDescriptionKey: "Configure an executable SPOT_NATIVE_PYTHON_BIN before launching spot.app."])
        }
        _ = try resolveLockedSSOTPath()
        try validateWritablePaths()
    }

    func resolveLockedSSOTPath() throws -> String {
        let path = nativeConfig.lockedSSOTPath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !path.isEmpty, FileManager.default.fileExists(atPath: path) else {
            throw NSError(domain: "SpotCoreService", code: 3, userInfo: [NSLocalizedDescriptionKey: "Locked SSOT path is missing."])
        }
        return path
    }

    func validateWritablePaths() throws {
        try FileManager.default.createDirectory(at: spotDataHome, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: spotLogHome, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: URL(fileURLWithPath: nativeConfig.runsDir), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: URL(fileURLWithPath: nativeConfig.intakeWatchDir), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: URL(fileURLWithPath: nativeConfig.intakeArchiveDir), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try FileManager.default.createDirectory(at: URL(fileURLWithPath: nativeConfig.intakeFailedDir), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    }

    func validateLoopbackBaseURL(_ url: URL) -> Bool {
        url.host == preferredHost || url.host == "localhost"
    }

    var activeRunProcessingStats: SpotProcessingStats? {
        latestRunDetail?.processingStats
            ?? selectedOverviewRunSummary?.processingStats
            ?? selectedOverviewRunSummary?.run?.processingStats
            ?? selectedRunRecord?.progress.flatMap { progress in
                SpotProcessingStats(
                    updatedAt: nil,
                    processedRows: progress.processedRows,
                    totalRows: progress.totalRows,
                    elapsedSeconds: nil,
                    avgSecondsPerRow: nil,
                    threatRowsDetected: nil,
                    threatRate: nil,
                    projectedThreatRows: nil,
                    reviewRequiredRowsDetected: nil,
                    judgedRows: nil
                )
            }
    }

    var activeRunUploadID: String? {
        latestRunDetail?.uploadID ?? selectedOverviewRunSummary?.uploadID
    }

    var activeRunProgressPercentage: Double? {
        latestRunDetail?.progress?.progressPercentage
            ?? selectedOverviewRunSummary?.rowProgressPercentage
            ?? selectedOverviewRunSummary?.run?.rowProgressPercentage
            ?? selectedRunRecord?.progress?.progressPercentage
    }

    var activeRunCurrentSegment: SpotActiveSegment? {
        latestRunDetail?.segmentSummary?.activeSegment
    }

    var activeReviewRequiredRate: Double? {
        guard let processed = activeRunProcessedRows, processed > 0 else { return nil }
        guard let reviewRequired = activeRunProcessingStats?.reviewRequiredRowsDetected else { return nil }
        return Double(reviewRequired) / Double(processed)
    }

    var activeThreatRateRatio: Double? {
        activeRunProcessingStats?.threatRate
    }

    var historicalBaseline: SpotHistoricalBaseline {
        let merged = mergeRunRecords(primary: availableRuns, fallback: loadLocalRunRecords())
        let stats = merged.compactMap(\.processingStats)

        let avgSeconds = stats.compactMap(\.avgSecondsPerRow)
        let reviewRates = stats.compactMap { stat -> Double? in
            guard let processed = stat.processedRows, processed > 0,
                  let reviewRequired = stat.reviewRequiredRowsDetected else { return nil }
            return Double(reviewRequired) / Double(processed)
        }
        let threatRates = stats.compactMap(\.threatRate)

        return SpotHistoricalBaseline(
            avgSecondsPerRow: average(of: avgSeconds),
            reviewRequiredRate: average(of: reviewRates),
            threatRate: average(of: threatRates)
        )
    }

    var historicalRunRecords: [SpotRunRecord] {
        mergeRunRecords(primary: availableRuns, fallback: loadLocalRunRecords())
    }

    func metricHistorySeries(_ kind: SpotMetricHistoryKind, limit: Int = 8) -> [Double] {
        let records = historicalRunRecords
        let values: [Double] = records.compactMap { record -> Double? in
            switch kind {
            case .processedRows:
                if let value = record.processingStats?.processedRows {
                    return Double(value)
                }
                if let value = record.progress?.processedRows {
                    return Double(value)
                }
                return nil
            case .totalRows:
                if let value = record.processingStats?.totalRows {
                    return Double(value)
                }
                if let value = record.progress?.totalRows {
                    return Double(value)
                }
                return nil
            case .progressPercent:
                return record.progress?.progressPercentage
            case .avgSecondsPerRow:
                return record.processingStats?.avgSecondsPerRow
            case .elapsedSeconds:
                if let value = record.processingStats?.elapsedSeconds {
                    return Double(value)
                }
                return nil
            case .reviewRequiredRows:
                if let value = record.processingStats?.reviewRequiredRowsDetected {
                    return Double(value)
                }
                return nil
            case .pendingReviewRows:
                if let value = record.reviewSummary?.pendingRows {
                    return Double(value)
                }
                return nil
            case .segmentQueue:
                return nil
            case .runRecords:
                return nil
            case .acceptedUploads:
                return nil
            case .rowsRemaining:
                guard let total = record.processingStats?.totalRows ?? record.progress?.totalRows,
                      let processed = record.processingStats?.processedRows ?? record.progress?.processedRows else { return nil }
                return Double(max(total - processed, 0))
            case .threatRate:
                return record.processingStats?.threatRate.map { $0 * 100 }
            case .projectedThreats:
                return record.processingStats?.projectedThreatRows.map(Double.init)
            case .judgedRows:
                return record.processingStats?.judgedRows.map(Double.init)
            }
        }

        let tail = Array(values.prefix(limit).reversed())

        let currentValue: Double? = switch kind {
        case .processedRows:
            if let value = activeRunProcessedRows { Double(value) } else { nil }
        case .totalRows:
            if let value = activeRunTotalRows { Double(value) } else { nil }
        case .progressPercent:
            activeRunProgressPercentage
        case .avgSecondsPerRow:
            activeRunProcessingStats?.avgSecondsPerRow
        case .elapsedSeconds:
            if let value = activeRunProcessingStats?.elapsedSeconds { Double(value) } else { nil }
        case .reviewRequiredRows:
            if let value = activeRunProcessingStats?.reviewRequiredRowsDetected { Double(value) } else { nil }
        case .pendingReviewRows:
            Double(pendingReviewCount)
        case .segmentQueue:
            if let value = operationsOverview?.totalSegments { Double(value) } else { nil }
        case .runRecords:
            Double(availableRuns.count)
        case .acceptedUploads:
            Double(max((operationsOverview?.recentUploads.filter { ($0.status ?? "").lowercased() == "accepted" }.count ?? 0), availableUploads.count))
        case .rowsRemaining:
            if let value = activeRowsRemainingValue { Double(value) } else { nil }
        case .threatRate:
            activeRunProcessingStats?.threatRate.map { $0 * 100 }
        case .projectedThreats:
            if let value = activeRunProcessingStats?.projectedThreatRows { Double(value) } else { nil }
        case .judgedRows:
            if let value = activeRunProcessingStats?.judgedRows { Double(value) } else { nil }
        }

        var result = tail
        if let currentValue {
            result.append(currentValue)
        }
        return result
    }

    var activeRunProcessedRows: Int? {
        latestRunDetail?.progress?.processedRows
            ?? selectedOverviewRunSummary?.run?.processedRows
            ?? selectedRunRecord?.progress?.processedRows
    }

    var activeRunTotalRows: Int? {
        latestRunDetail?.progress?.totalRows
            ?? selectedOverviewRunSummary?.run?.totalRows
            ?? selectedOverviewRunSummary?.rowCount
            ?? selectedRunRecord?.progress?.totalRows
    }

    var activeRowsRemainingValue: Int? {
        guard let total = activeRunTotalRows, let processed = activeRunProcessedRows else { return nil }
        return max(total - processed, 0)
    }

    var hasVisibleActiveRun: Bool {
        !activeRunSummary.selectedRunID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        activeRunSummary.runState != "-"
    }

    var canPauseActiveRun: Bool {
        guard hasVisibleActiveRun else { return false }
        guard let ops = latestRunDetail?.availableOperations else { return false }
        return ops.pause
    }

    var canResumeActiveRun: Bool {
        guard hasVisibleActiveRun else { return false }
        guard let ops = latestRunDetail?.availableOperations else { return false }
        return ops.resume
    }

    var canCancelActiveRun: Bool {
        guard hasVisibleActiveRun else { return false }
        guard let ops = latestRunDetail?.availableOperations else { return false }
        return ops.cancel
    }

    var canRetrySelectedRun: Bool {
        guard hasVisibleActiveRun else { return false }
        guard let ops = latestRunDetail?.availableOperations else { return false }
        return ops.retry
    }

    var canRecoverSelectedRun: Bool {
        guard hasVisibleActiveRun else { return false }
        guard let ops = latestRunDetail?.availableOperations else { return false }
        return ops.recover
    }

    func redactSensitiveLogLine(_ line: String) -> String {
        line.replacingOccurrences(of: nativeConfig.accessCode, with: nativeConfig.accessCode.isEmpty ? "" : "<redacted>")
    }

    private func processWatchedIntakeDirectory(forceScan: Bool = false) async {
        guard baseURL != nil else {
            refreshWatchFolderStatus()
            return
        }
        let watchURL = URL(fileURLWithPath: nativeConfig.intakeWatchDir)
        do {
            try validateWritablePaths()
            let candidateFiles = try FileManager.default.contentsOfDirectory(
                at: watchURL,
                includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey, .isRegularFileKey],
                options: [.skipsHiddenFiles]
            )
            .filter { $0.pathExtension.lowercased() == "xlsx" }

            let activePaths = Set(candidateFiles.map(\.path))
            watchedFileSnapshots = watchedFileSnapshots.filter { activePaths.contains($0.key) }

            guard !candidateFiles.isEmpty else {
                refreshWatchFolderStatus()
                await autoStartPendingAcceptedUploadIfPossible()
                return
            }

            for fileURL in candidateFiles.sorted(by: { $0.lastPathComponent.localizedCaseInsensitiveCompare($1.lastPathComponent) == .orderedAscending }) {
                if watchFolderInFlight.contains(fileURL.path) {
                    continue
                }
                let resourceValues = try fileURL.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey, .isRegularFileKey])
                guard resourceValues.isRegularFile == true else { continue }
                let size = UInt64(resourceValues.fileSize ?? 0)
                let modifiedAt = resourceValues.contentModificationDate ?? .distantPast
                let activityID = inboxActivityID(for: fileURL, size: size, modifiedAt: modifiedAt)
                let prior = watchedFileSnapshots[fileURL.path]
                let isStableNow = prior?.size == size && prior?.modifiedAt == modifiedAt
                let stablePasses = isStableNow ? (prior?.stablePasses ?? 0) + 1 : 0
                watchedFileSnapshots[fileURL.path] = WatchedFileSnapshot(size: size, modifiedAt: modifiedAt, stablePasses: stablePasses)

                let age = Date().timeIntervalSince(modifiedAt)
                let readyForIntake = forceScan || (stablePasses >= 1 && age >= 3)
                guard readyForIntake else { continue }

                watchFolderInFlight.insert(fileURL.path)
                defer { watchFolderInFlight.remove(fileURL.path) }

                do {
                    upsertInboxActivity(
                        id: activityID,
                        filename: fileURL.lastPathComponent,
                        sourcePath: fileURL.path,
                        sourceBytes: size,
                        stage: "intake_started",
                        note: "Workbook is stable and intake has started."
                    )
                    let record = try await performWorkbookIntake(fileURL: fileURL)
                    appendLog("Watch intake accepted \(fileURL.lastPathComponent) as \(record.uploadID).")
                    upsertInboxActivity(
                        id: activityID,
                        filename: record.filename ?? fileURL.lastPathComponent,
                        sourcePath: fileURL.path,
                        sourceBytes: size,
                        stage: "accepted",
                        note: "Workbook passed intake validation and is queued in {spot}.",
                        uploadID: record.uploadID
                    )
                    await refreshUploads()
                    await refreshOperationsOverview()
                    watchedFileSnapshots.removeValue(forKey: fileURL.path)
                    do {
                        let destinationURL = try finalizeAcceptedWatchedFile(fileURL)
                        upsertInboxActivity(
                            id: activityID,
                            filename: record.filename ?? fileURL.lastPathComponent,
                            sourcePath: fileURL.path,
                            sourceBytes: size,
                            stage: "moved_to_processed",
                            note: "Workbook source file moved to processed after accepted intake.",
                            uploadID: record.uploadID,
                            destinationPath: destinationURL.path
                        )
                    } catch {
                        appendLog("Watch intake accepted but could not archive \(fileURL.lastPathComponent): \(error.localizedDescription)")
                        uploadMessage = "Accepted \(fileURL.lastPathComponent), but could not move it to the processed folder."
                        upsertInboxActivity(
                            id: activityID,
                            filename: record.filename ?? fileURL.lastPathComponent,
                            sourcePath: fileURL.path,
                            sourceBytes: size,
                            stage: "accepted_move_failed",
                            note: "Intake succeeded, but the source file could not be moved to processed: \(error.localizedDescription)",
                            uploadID: record.uploadID
                        )
                        continue
                    }
                    uploadMessage = "Queued \(fileURL.lastPathComponent) from the watch folder."
                    await autoStartPendingAcceptedUploadIfPossible()
                } catch {
                    appendLog("Watch intake failed for \(fileURL.lastPathComponent): \(error.localizedDescription)")
                    uploadMessage = "Watch-folder intake failed for \(fileURL.lastPathComponent): \(error.localizedDescription)"
                    let failurePath = try? finalizeRejectedWatchedFile(fileURL).path
                    upsertInboxActivity(
                        id: activityID,
                        filename: fileURL.lastPathComponent,
                        sourcePath: fileURL.path,
                        sourceBytes: size,
                        stage: "failed",
                        note: "Workbook intake failed: \(error.localizedDescription)",
                        destinationPath: failurePath
                    )
                    watchedFileSnapshots.removeValue(forKey: fileURL.path)
                }
            }

            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount())
            await autoStartPendingAcceptedUploadIfPossible()
        } catch {
            watchFolderStatus = "Watch folder scan failed: \(error.localizedDescription)"
        }
    }

    private func performWorkbookIntake(fileURL: URL) async throws -> SpotUploadRecord {
        guard let baseURL else {
            throw NSError(domain: "SpotCoreService", code: 40, userInfo: [NSLocalizedDescriptionKey: "Runtime is not reachable yet."])
        }
        _ = try await ensureAuthenticated(baseURL: baseURL)
        let content = try Data(contentsOf: fileURL)
        let encodedFilename = fileURL.lastPathComponent.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? fileURL.lastPathComponent
        guard let uploadURL = URL(string: "\(baseURL.absoluteString)/uploads/intake?filename=\(encodedFilename)") else {
            throw NSError(domain: "SpotCoreService", code: 41, userInfo: [NSLocalizedDescriptionKey: "Could not construct upload URL."])
        }
        var request = URLRequest(url: uploadURL)
        request.httpMethod = "POST"
        request.httpBody = content
        request.setValue("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", forHTTPHeaderField: "Content-Type")
        return try await requestJSON(request: request)
    }

    private func autoStartPendingAcceptedUploadIfPossible() async {
        guard nativeConfig.autoStartWatchFolder else { return }
        guard let baseURL else { return }
        let blockingRunPresent: Bool
        do {
            blockingRunPresent = try await hasBlockingRunInFlight(baseURL: baseURL)
        } catch {
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount(), extra: "could not inspect live run state")
            return
        }
        guard !blockingRunPresent else {
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount(), extra: "waiting for the current run to finish before auto-starting the next workbook")
            return
        }
        let pendingUpload: SpotUploadRecord?
        do {
            pendingUpload = try await nextPendingAcceptedUpload(baseURL: baseURL)
        } catch {
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount(), extra: "could not inspect live queue state")
            return
        }
        guard let pendingUpload else {
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount())
            return
        }
        await autoStartRunIfPossible(uploadID: pendingUpload.uploadID, filename: pendingUpload.filename ?? pendingUpload.uploadID)
    }

    private func autoStartRunIfPossible(uploadID: String, filename: String) async {
        guard nativeConfig.autoStartWatchFolder else { return }
        guard let baseURL else { return }
        do {
            _ = try await ensureAuthenticated(baseURL: baseURL)
            selectedUploadID = uploadID
            let runID = autoRunID(for: filename)
            var payload: [String: Any] = [
                "upload_id": uploadID,
                "language": startLanguage,
                "review_mode": startReviewMode,
            ]
            if let limit = Int(startLimit.trimmingCharacters(in: .whitespacesAndNewlines)), limit > 0 {
                payload["limit"] = limit
            }
            var request = URLRequest(url: baseURL.appending(path: "classify/start/\(runID)"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])
            let _: SpotRunStartResponse = try await requestJSON(request: request)
            uploadMessage = "Auto-started run \(runID) from watched workbook \(filename)."
            appendLog("Watch folder started run \(runID) from upload \(uploadID).")
            upsertInboxActivityForUpload(
                uploadID: uploadID,
                stage: "run_started",
                note: "Workbook started as native run \(runID).",
                runID: runID
            )
            primeVisibleRunFromInboxHistory(force: true)
            newRunID = suggestedRunID()
            await refreshHealth()
            await refreshUploads()
            await refreshOperationsOverview()
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount())
        } catch {
            appendLog("Auto-start skipped for \(filename): \(error.localizedDescription)")
            upsertInboxActivityForUpload(
                uploadID: uploadID,
                stage: "waiting_for_run_start",
                note: "Workbook is accepted, but run start is deferred: \(error.localizedDescription)"
            )
            refreshWatchFolderStatus(pendingFiles: pendingWatchFileCount(), extra: "intake queued, but auto-start could not launch yet")
        }
    }

    private func autoRunID(for filename: String) -> String {
        let stem = URL(fileURLWithPath: filename).deletingPathExtension().lastPathComponent
        let slug = stem
            .lowercased()
            .replacingOccurrences(of: "[^a-z0-9]+", with: "-", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let prefix = slug.isEmpty ? "run" : String(slug.prefix(40))
        return "\(prefix)-\(formatter.string(from: Date()))"
    }

    private func pendingWatchFileCount() -> Int {
        let watchURL = URL(fileURLWithPath: nativeConfig.intakeWatchDir)
        let files = (try? FileManager.default.contentsOfDirectory(at: watchURL, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
        return files.filter { $0.pathExtension.lowercased() == "xlsx" }.count
    }

    private func finalizeAcceptedWatchedFile(_ sourceURL: URL) throws -> URL {
        try moveWatchedFile(sourceURL, to: URL(fileURLWithPath: nativeConfig.intakeArchiveDir))
    }

    private func finalizeRejectedWatchedFile(_ sourceURL: URL) throws -> URL {
        try moveWatchedFile(sourceURL, to: URL(fileURLWithPath: nativeConfig.intakeFailedDir))
    }

    private func moveWatchedFile(_ sourceURL: URL, to directoryURL: URL) throws -> URL {
        guard FileManager.default.fileExists(atPath: sourceURL.path) else { return directoryURL.appending(path: sourceURL.lastPathComponent) }
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let destinationURL = uniqueArchiveURL(for: sourceURL, in: directoryURL)
        do {
            try FileManager.default.moveItem(at: sourceURL, to: destinationURL)
        } catch {
            do {
                try FileManager.default.copyItem(at: sourceURL, to: destinationURL)
                try FileManager.default.removeItem(at: sourceURL)
            } catch {
                throw error
            }
        }
        return destinationURL
    }

    private func uniqueArchiveURL(for sourceURL: URL, in directoryURL: URL) -> URL {
        var candidate = directoryURL.appending(path: sourceURL.lastPathComponent)
        if !FileManager.default.fileExists(atPath: candidate.path) {
            return candidate
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let stem = sourceURL.deletingPathExtension().lastPathComponent
        let ext = sourceURL.pathExtension
        let stampedName = "\(stem)-\(formatter.string(from: Date())).\(ext)"
        candidate = directoryURL.appending(path: stampedName)
        return candidate
    }

    private func refreshWatchFolderStatus(pendingFiles: Int? = nil, extra: String? = nil) {
        let pending = pendingFiles ?? pendingWatchFileCount()
        let autoStart = nativeConfig.autoStartWatchFolder ? "auto-start on" : "auto-start off"
        watchFolderStatus = "Watching \(nativeConfig.intakeWatchDir) · \(pending) pending .xlsx files · \(autoStart)\(extra.map { " · \($0)" } ?? "")"
    }

    private func inboxActivityID(for sourceURL: URL, size: UInt64, modifiedAt: Date) -> String {
        let stamp = Int(modifiedAt.timeIntervalSince1970)
        return "\(sourceURL.path)#\(size)#\(stamp)"
    }

    private func upsertInboxActivity(
        id: String,
        filename: String,
        sourcePath: String,
        sourceBytes: UInt64,
        stage: String,
        note: String,
        uploadID: String? = nil,
        runID: String? = nil,
        destinationPath: String? = nil
    ) {
        let now = Date().timeIntervalSince1970
        let newEvent = SpotInboxDocumentEvent(
            id: "\(id)#\(Int(now * 1000))#\(stage)",
            stage: stage,
            note: note,
            createdAt: now,
            uploadID: uploadID,
            runID: runID,
            destinationPath: destinationPath
        )
        if let index = inboxActivities.firstIndex(where: { $0.id == id }) {
            inboxActivities[index].filename = filename
            inboxActivities[index].sourcePath = sourcePath
            inboxActivities[index].sourceBytes = sourceBytes
            inboxActivities[index].stage = stage
            inboxActivities[index].note = note
            inboxActivities[index].uploadID = uploadID ?? inboxActivities[index].uploadID
            inboxActivities[index].runID = runID ?? inboxActivities[index].runID
            inboxActivities[index].destinationPath = destinationPath ?? inboxActivities[index].destinationPath
            inboxActivities[index].updatedAt = now
            let duplicateLatest = inboxActivities[index].events.last.map {
                $0.stage == newEvent.stage &&
                $0.note == newEvent.note &&
                $0.uploadID == newEvent.uploadID &&
                $0.runID == newEvent.runID &&
                $0.destinationPath == newEvent.destinationPath
            } ?? false
            if !duplicateLatest {
                inboxActivities[index].events.append(newEvent)
            }
        } else {
            inboxActivities.append(
                SpotInboxDocumentActivity(
                    id: id,
                    filename: filename,
                    sourcePath: sourcePath,
                    sourceBytes: sourceBytes,
                    stage: stage,
                    note: note,
                    uploadID: uploadID,
                    runID: runID,
                    destinationPath: destinationPath,
                    detectedAt: now,
                    updatedAt: now,
                    events: [newEvent]
                )
            )
        }
        inboxActivities.sort { $0.updatedAt > $1.updatedAt }
        if inboxActivities.count > 50 {
            inboxActivities = Array(inboxActivities.prefix(50))
        }
        saveInboxActivities()
    }

    private func upsertInboxActivityForUpload(
        uploadID: String,
        stage: String,
        note: String,
        runID: String? = nil
    ) {
        guard let index = inboxActivities.firstIndex(where: { $0.uploadID == uploadID }) else { return }
        upsertInboxActivity(
            id: inboxActivities[index].id,
            filename: inboxActivities[index].filename,
            sourcePath: inboxActivities[index].sourcePath,
            sourceBytes: inboxActivities[index].sourceBytes,
            stage: stage,
            note: note,
            uploadID: uploadID,
            runID: runID ?? inboxActivities[index].runID,
            destinationPath: inboxActivities[index].destinationPath
        )
    }

    private func hasBlockingRunInFlight(baseURL: URL) async throws -> Bool {
        let runs: [SpotRunRecord] = try await requestJSON(url: baseURL.appending(path: "runs"))
        for run in runs {
            guard let state = run.state?.uppercased(), ["STARTING", "PROCESSING", "PAUSED", "QUEUED"].contains(state) else {
                continue
            }
            if let liveStatus: SpotClassifyStatus = try? await requestJSON(url: baseURL.appending(path: "classify/status/\(run.runID)")) {
                if liveStatus.running || liveStatus.paused {
                    return true
                }
                continue
            }
            return true
        }
        return false
    }

    private func nextPendingAcceptedUpload(baseURL: URL) async throws -> SpotUploadRecord? {
        let uploads: [SpotUploadRecord] = try await requestJSON(url: baseURL.appending(path: "uploads"))
        let overview: SpotOperationsOverview = try await requestJSON(url: baseURL.appending(path: "operations/overview"))
        operationsOverview = overview
        availableUploads = uploads

        let uploadByID = Dictionary(uniqueKeysWithValues: uploads.map { ($0.uploadID, $0) })
        for summary in overview.recentUploads {
            let status = (summary.status ?? "").lowercased()
            let hasRun = !(summary.run?.runID ?? "").isEmpty
            if status == "accepted", !hasRun, let upload = uploadByID[summary.uploadID] {
                return upload
            }
        }

        let uploadsWithRuns = Set(overview.recentUploads.compactMap { summary in
            let hasRun = !(summary.run?.runID ?? "").isEmpty
            return hasRun ? summary.uploadID : nil
        })

        return uploads.first(where: { ($0.status ?? "").lowercased() == "accepted" && !uploadsWithRuns.contains($0.uploadID) })
    }

    private func attemptAutomaticRuntimeRecoveryIfNeeded() {
        guard runtimeAutoRecoveryEnabled else { return }
        let now = Date()
        if let lastAutoLaunchAttemptAt, now.timeIntervalSince(lastAutoLaunchAttemptAt) < 15 {
            return
        }
        lastAutoLaunchAttemptAt = now
        launchSpot()
    }

    private func gracefulStopRuntime(suspendActiveRuns: Bool) async {
        appendSupervisorLog("gracefulStopRuntime started; suspendActiveRuns=\(suspendActiveRuns)")
        if suspendActiveRuns, let baseURL {
            do {
                _ = try await requestRuntimeSuspend(baseURL: baseURL)
                appendSupervisorLog("gracefulStopRuntime requested backend suspend")
            } catch {
                appendLog("Native supervisor could not suspend active runs before shutdown: \(error.localizedDescription)")
                appendSupervisorLog("gracefulStopRuntime suspend request failed: \(error.localizedDescription)")
            }
        }

        if let launchProcess, launchProcess.isRunning {
            launchProcess.terminate()
            let deadline = Date().addingTimeInterval(5)
            while launchProcess.isRunning && Date() < deadline {
                try? await Task.sleep(for: .milliseconds(100))
            }
            if launchProcess.isRunning {
                launchProcess.interrupt()
            }
            self.launchProcess = nil
        }

        let pkill = Process()
        pkill.executableURL = URL(fileURLWithPath: "/usr/bin/pkill")
        pkill.arguments = ["-f", "launch-bundled-appliance.sh|uvicorn backend.main:app"]
        pkill.standardOutput = Pipe()
        pkill.standardError = Pipe()
        try? pkill.run()
        runtimeState = .offline
        baseURL = nil
        appendSupervisorLog("gracefulStopRuntime completed")
    }

    private func requestRuntimeSuspend(baseURL: URL) async throws -> SpotRuntimeSuspendResponse {
        _ = try await ensureAuthenticated(baseURL: baseURL)
        var request = URLRequest(url: baseURL.appending(path: "native/runtime/suspend"))
        request.httpMethod = "POST"
        request.timeoutInterval = 6
        return try await requestJSON(request: request)
    }

    private func chooseDirectory(title: String, message: String, apply: (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.title = title
        panel.message = message
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Use Folder"
        if panel.runModal() == .OK, let url = panel.url {
            apply(url)
            saveNativeConfig()
            refreshWatchFolderStatus()
        }
    }

    private func launchEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["SPOT_NATIVE_PYTHON_BIN"] = nativeConfig.pythonBin
        env["SPOT_NATIVE_RUNS_DIR"] = nativeConfig.runsDir
        env["SPOT_NATIVE_LOGS_DIR"] = nativeConfig.logsDir
        env["SPOT_LOCKED_SSOT_PATH"] = nativeConfig.lockedSSOTPath
        env["SPOT_PRODUCTION_MODE"] = "1"
        env["SPOT_RUN_PREFLIGHT"] = "1"
        env["SPOT_AUTH_ENABLED"] = "0"
        env["SPOT_NATIVE_PORT"] = String(nativeConfig.port)
        env["SPOT_NATIVE_SUPERVISOR_PID"] = String(ProcessInfo.processInfo.processIdentifier)
        if !nativeConfig.accessCode.isEmpty {
            env["SPOT_LOCAL_ACCESS_CODE"] = nativeConfig.accessCode
        }
        return env
    }

    private func appendLog(_ raw: String) {
        let trimmed = raw
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .map(redactSensitiveLogLine(_:))
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        guard !trimmed.isEmpty else { return }
        logLines.append(contentsOf: trimmed.suffix(10))
        if logLines.count > 200 {
            logLines.removeFirst(logLines.count - 200)
        }
        for line in trimmed {
            appendSupervisorLog("runtime> \(line)")
        }
    }

    private func detectReachableRuntime() async -> (URL, SpotHealthConfig)? {
        let url = URL(string: "http://\(preferredHost):\(nativeConfig.port)/api/health")!
        do {
            let payload: SpotHealthConfig = try await requestJSON(url: url)
            guard payload.ok, payload.launch.ready, payload.status == "online" else { return nil }
            guard validateLoopbackBaseURL(url) else { return nil }
            let rootURL = URL(string: "http://\(preferredHost):\(nativeConfig.port)")!
            return (rootURL, payload)
        } catch {
            return nil
        }
    }

    private func waitForRuntimeReadyAfterLaunch(maxWaitSeconds: Int = 20) async {
        for _ in 0..<maxWaitSeconds {
            await refreshHealth()
            if case .online = runtimeState {
                return
            }
            if case .error = runtimeState {
                return
            }
            try? await Task.sleep(for: .seconds(1))
        }
    }

    private func requestJSON<T: Decodable>(url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        return try await requestJSON(request: request)
    }

    private func requestJSON<T: Decodable>(url: URL, timeoutInterval: TimeInterval) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = timeoutInterval
        return try await requestJSON(request: request)
    }

    private func requestJSON<T: Decodable>(request: URLRequest) async throws -> T {
        var request = request
        if request.timeoutInterval <= 0 {
            request.timeoutInterval = 15
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw NSError(domain: "SpotCoreService", code: 4, userInfo: [NSLocalizedDescriptionKey: "Runtime probe failed."])
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func refreshAuthenticatedSnapshot(rootURL: URL) async throws {
        let auth = try await ensureAuthenticated(baseURL: rootURL)
        authEnabledForNativeApp = auth.authEnabled
        if !auth.authEnabled {
            authSummary = "Native local mode · authentication disabled."
            operatorRole = "admin"
            operatorActorName = "local-admin"
        } else if let session = auth.session {
            operatorRole = session.role
            operatorActorName = session.actorName
            authSummary = "Authenticated as \(session.actorName) · role \(session.role) · local auth enabled."
        } else if auth.authEnabled {
            authSummary = "Authentication required but no session is active."
        } else {
            authSummary = "Auth disabled; local admin session is implied."
        }

        primeVisibleRunFromInboxHistory()

        let runs: [SpotRunRecord]
        do {
            runs = try await requestJSON(url: rootURL.appending(path: "runs"), timeoutInterval: 2.5)
        } catch {
            runs = []
        }
        let candidateRuns = mergeRunRecords(primary: runs, fallback: fallbackRunsFromLocalState())
        availableRuns = candidateRuns

        if await autoResumeInterruptedRunIfNeeded(baseURL: rootURL, runs: candidateRuns) {
            let resumedRuns = ((try? await requestJSON(url: rootURL.appending(path: "runs"), timeoutInterval: 2.5)) as [SpotRunRecord]?) ?? candidateRuns
            availableRuns = mergeRunRecords(primary: resumedRuns, fallback: fallbackRunsFromLocalState())
        }

        let overview = try? await requestJSON(url: rootURL.appending(path: "operations/overview"), timeoutInterval: 2.5) as SpotOperationsOverview
        operationsOverview = overview
        let uploads = (try? await requestJSON(url: rootURL.appending(path: "uploads"), timeoutInterval: 2.5) as [SpotUploadRecord]) ?? loadLocalUploadRecords()
        availableUploads = uploads
        if selectedUploadID.isEmpty, let firstAccepted = uploads.first(where: { ($0.status ?? "").lowercased() == "accepted" }) {
            selectedUploadID = firstAccepted.uploadID
        }

        guard let preferredRunID = preferredRunID(from: availableRuns, overview: overview) else {
            selectedRunID = ""
            pendingReviewCount = 0
            reviewPreviewRows = []
            activeRunSummary = SpotRuntimeSummary(
                healthDescription: activeRunSummary.healthDescription,
                reviewPending: 0,
                selectedRunID: "",
                runState: "-",
                runLanguage: "-",
                reviewMode: "-",
                progressDescription: "No runs found under the current runs directory.",
                authenticatedAs: authSummary,
                nextActions: [],
                outputReady: false
            )
            return
        }

        if selectedRunID != preferredRunID {
            selectedRunID = preferredRunID
        }
        do {
            let detail: SpotRunDetail = try await requestJSON(url: rootURL.appending(path: "runs/\(selectedRunID)/detail"), timeoutInterval: 3)
            applyRunDetail(detail)
            try await loadReviewQueue(for: selectedRunID)
        } catch {
            do {
                try await applyLightweightRunStatus(baseURL: rootURL, runID: selectedRunID)
                reviewQueueRows = []
                activeReviewInspector = nil
                reviewDraft = .empty
            } catch {
                primeVisibleRunFromInboxHistory(force: true)
            }
        }
    }

    private func ensureAuthenticated(baseURL: URL) async throws -> SpotAuthSessionResponse {
        let sessionURL = baseURL.appending(path: "auth/session")
        let existing: SpotAuthSessionResponse = try await requestJSON(url: sessionURL)
        let desiredRole = normalizedOperatorRole()
        let desiredActor = normalizedOperatorActor()
        if existing.authenticated, let session = existing.session, session.role == desiredRole, session.actorName == desiredActor {
            return existing
        }
        if !existing.authEnabled {
            return existing
        }
        return try await loginAsRole(baseURL: baseURL, role: desiredRole, actorName: desiredActor)
    }

    private func loginAsRole(baseURL: URL, role: String, actorName: String) async throws -> SpotAuthSessionResponse {
        let sessionURL = baseURL.appending(path: "auth/session")
        let existing: SpotAuthSessionResponse = try await requestJSON(url: sessionURL)
        if existing.authenticated, let session = existing.session, session.role == role {
            return existing
        }
        if !existing.authEnabled {
            return existing
        }

        var request = URLRequest(url: baseURL.appending(path: "auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let payload = [
            "access_code": localAccessCode(),
            "role": role,
            "actor_name": actorName,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [])
        return try await requestJSON(request: request)
    }

    private func localAccessCode() -> String {
        let configured = operatorAccessCode.trimmingCharacters(in: .whitespacesAndNewlines)
        if !configured.isEmpty {
            return configured
        }
        let fallback = nativeConfig.accessCode.trimmingCharacters(in: .whitespacesAndNewlines)
        if !fallback.isEmpty {
            return fallback
        }
        return "spot-local"
    }

    private func normalizedOperatorRole() -> String {
        let trimmed = operatorRole.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "operator" : trimmed
    }

    private func normalizedOperatorActor() -> String {
        let trimmed = operatorActorName.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "local-operator" : trimmed
    }

    private func localAccessCodeDeprecated() -> String {
        let configured = nativeConfig.accessCode.trimmingCharacters(in: .whitespacesAndNewlines)
        return configured.isEmpty ? "spot-local" : configured
    }

    private func preferredRunID(from runs: [SpotRunRecord], overview: SpotOperationsOverview?) -> String? {
        let prioritizedRuns = runs.sorted(by: sortRunsForPrimarySelection)
        if !selectedRunID.isEmpty, let selected = prioritizedRuns.first(where: { $0.runID == selectedRunID }), isActiveRunState(selected.state) {
            return selectedRunID
        }
        if let active = prioritizedRuns.first(where: { isActiveRunState($0.state) }) {
            return active.runID
        }
        if let newestCreatedAt = runs.compactMap(\.createdAt).max() {
            let newestRuns = runs
                .filter { ($0.createdAt ?? 0) == newestCreatedAt }
                .sorted(by: sortRunsForPrimarySelection)
            if let newest = newestRuns.first {
                return newest.runID
            }
        }
        if let runID = overview?.recentUploads.compactMap({ $0.run?.runID }).first, !runID.isEmpty {
            return runID
        }
        if let runID = inboxActivities.compactMap({ $0.runID }).first, !runID.isEmpty {
            return runID
        }
        if let first = prioritizedRuns.first?.runID {
            return first
        }
        return nil
    }

    private func autoResumeInterruptedRunIfNeeded(baseURL: URL, runs: [SpotRunRecord]) async -> Bool {
        guard !runs.contains(where: { isActiveRunState($0.state) }) else { return false }
        let prioritizedRuns = runs.sorted(by: sortRunsForPrimarySelection)
        let newestCreatedAt = runs.compactMap(\.createdAt).max() ?? 0
        for run in prioritizedRuns {
            let normalizedState = run.state?.uppercased() ?? ""
            guard ["INTERRUPTED", "FAILED"].contains(normalizedState) else { continue }
            let runCreatedAt = run.createdAt ?? 0
            guard runCreatedAt >= newestCreatedAt else {
                appendLog("Skipping auto-recovery for \(run.runID) because newer run history exists.")
                continue
            }
            if let lastAttempt = autoRecoveryAttemptedRunIDs[run.runID], Date().timeIntervalSince(lastAttempt) < 15 {
                continue
            }
            autoRecoveryAttemptedRunIDs[run.runID] = Date()
            do {
                let detail: SpotRunDetail = try await requestJSON(
                    url: baseURL.appending(path: "runs/\(run.runID)/detail"),
                    timeoutInterval: 10
                )
                guard detail.recovery?.canResumeWorker == true else { continue }
                if await recoverRunAndWaitUntilActive(baseURL: baseURL, runID: run.runID) {
                    selectedRunID = run.runID
                    appendLog("Auto-recovered interrupted run \(run.runID) during native runtime startup.")
                    artifactMessage = "Recovered interrupted run \(run.runID) after native runtime restart."
                    return true
                }
                appendLog("Auto-recovery did not activate run \(run.runID) before the startup recovery deadline.")
            } catch {
                appendLog("Auto-recovery skipped for \(run.runID): \(error.localizedDescription)")
            }
        }
        return false
    }

    private func sortRunsForPrimarySelection(_ lhs: SpotRunRecord, _ rhs: SpotRunRecord) -> Bool {
        let lhsState = (lhs.state ?? "").uppercased()
        let rhsState = (rhs.state ?? "").uppercased()
        let lhsRank = primarySelectionRank(for: lhsState)
        let rhsRank = primarySelectionRank(for: rhsState)
        if lhsRank != rhsRank {
            return lhsRank < rhsRank
        }
        let lhsCreated = lhs.createdAt ?? 0
        let rhsCreated = rhs.createdAt ?? 0
        if lhsCreated != rhsCreated {
            return lhsCreated > rhsCreated
        }
        return lhs.runID > rhs.runID
    }

    private func primarySelectionRank(for state: String) -> Int {
        switch state {
        case "STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED", "QUEUED":
            return 0
        case "INTERRUPTED":
            return 1
        case "FAILED":
            return 2
        case "CANCELLED":
            return 3
        case "COMPLETED":
            return 4
        default:
            return 5
        }
    }

    private func selfHealRuntimeIfNeeded() async {
        guard runtimeAutoRecoveryEnabled else { return }
        guard case .online = runtimeState else { return }
        guard let baseURL else { return }
        guard !automaticHealingInFlight else { return }

        if let action = await automaticRunHealingAction(baseURL: baseURL) {
            automaticHealingInFlight = true
            defer { automaticHealingInFlight = false }
            switch action {
            case let .recover(runID, reason):
                appendLog("Native supervisor auto-recovering \(runID): \(reason)")
                _ = await recoverRunAndWaitUntilActive(baseURL: baseURL, runID: runID)
            case let .heal(runID, reason):
                appendLog("Native supervisor auto-healing \(runID): \(reason)")
                _ = await healRunAndWaitUntilActive(baseURL: baseURL, runID: runID)
            }
            await refreshHealth()
        }
    }

    private func automaticRunHealingAction(baseURL: URL) async -> AutomaticRunHealingAction? {
        let runs = availableRuns.isEmpty ? fallbackRunsFromLocalState() : availableRuns
        guard let runID = preferredRunID(from: runs, overview: operationsOverview), !runID.isEmpty else {
            return nil
        }
        let detail: SpotRunDetail
        if latestRunDetail?.runID == runID, let latestRunDetail {
            detail = latestRunDetail
        } else if let fetched: SpotRunDetail = try? await requestJSON(
            url: baseURL.appending(path: "runs/\(runID)/detail"),
            timeoutInterval: 3
        ) {
            detail = fetched
        } else {
            return nil
        }
        let normalizedState = detail.state.uppercased()
        if let lastAttempt = autoHealingAttemptedRunIDs[runID], Date().timeIntervalSince(lastAttempt) < 45 {
            return nil
        }

        if ["INTERRUPTED", "FAILED"].contains(normalizedState), detail.recovery?.canResumeWorker == true {
            autoHealingAttemptedRunIDs[runID] = Date()
            return .recover(runID: runID, reason: "run is \(normalizedState.lowercased()) and has resumable worker state")
        }

        guard isActiveRunState(normalizedState) else { return nil }

        if detail.recovery?.running == false, detail.recovery?.canResumeWorker == true {
            autoHealingAttemptedRunIDs[runID] = Date()
            return .heal(runID: runID, reason: "run is marked active but no live worker is attached")
        }

        guard let processedRows = detail.progress?.processedRows ?? detail.processingStats?.processedRows else {
            return nil
        }
        let now = Date()
        let statsUpdatedAt = parseStatsUpdatedAt(detail.processingStats)
        let lastObserved = runHealthObservations[runID]
        runHealthObservations[runID] = RunHealthObservation(
            processedRows: processedRows,
            observedAt: now,
            statsUpdatedAt: statsUpdatedAt
        )
        guard let lastObserved else { return nil }
        guard processedRows <= lastObserved.processedRows else { return nil }

        let noProgressSeconds = now.timeIntervalSince(lastObserved.observedAt)
        let staleStatsSeconds = statsUpdatedAt.map { now.timeIntervalSince($0) } ?? noProgressSeconds
        let isStarting = ["STARTING", "PENDING", "VALIDATING"].contains(normalizedState)
        let threshold: TimeInterval = isStarting ? 60 : 90
        guard noProgressSeconds >= threshold, staleStatsSeconds >= threshold else {
            return nil
        }

        autoHealingAttemptedRunIDs[runID] = Date()
        return .heal(
            runID: runID,
            reason: "no progress for \(Int(noProgressSeconds))s and stats heartbeat is stale by \(Int(staleStatsSeconds))s"
        )
    }

    private func recoverRunAndWaitUntilActive(baseURL: URL, runID: String) async -> Bool {
        var request = URLRequest(url: baseURL.appending(path: "runs/\(runID)/recover"))
        request.httpMethod = "POST"
        request.timeoutInterval = 20

        do {
            let _: SpotOperationResponse = try await requestJSON(request: request)
        } catch {
            appendLog("Auto-recovery request for \(runID) did not return cleanly: \(error.localizedDescription)")
        }

        let deadline = Date().addingTimeInterval(20)
        while Date() < deadline {
            if let status: SpotClassifyStatus = try? await requestJSON(
                url: baseURL.appending(path: "classify/status/\(runID)"),
                timeoutInterval: 2.5
            ) {
                if status.running || isActiveRunState(status.effectiveState) {
                    return true
                }
                let normalizedState = status.effectiveState.uppercased()
                if ["FAILED", "CANCELLED", "COMPLETED"].contains(normalizedState) {
                    return false
                }
            }
            if let detail: SpotRunDetail = try? await requestJSON(
                url: baseURL.appending(path: "runs/\(runID)/detail"),
                timeoutInterval: 3
            ) {
                if detail.recovery?.running == true || isActiveRunState(detail.state) {
                    return true
                }
                let normalizedState = detail.state.uppercased()
                if ["FAILED", "CANCELLED", "COMPLETED"].contains(normalizedState) {
                    return false
                }
            }
            try? await Task.sleep(for: .seconds(1))
        }
        return false
    }

    private func healRunAndWaitUntilActive(baseURL: URL, runID: String) async -> Bool {
        var request = URLRequest(url: baseURL.appending(path: "runs/\(runID)/heal"))
        request.httpMethod = "POST"
        request.timeoutInterval = 25

        do {
            let _: SpotOperationResponse = try await requestJSON(request: request)
        } catch {
            appendLog("Auto-heal request for \(runID) did not return cleanly: \(error.localizedDescription)")
        }

        let deadline = Date().addingTimeInterval(25)
        while Date() < deadline {
            if let status: SpotClassifyStatus = try? await requestJSON(
                url: baseURL.appending(path: "classify/status/\(runID)"),
                timeoutInterval: 2.5
            ) {
                if status.running || isActiveRunState(status.effectiveState) {
                    return true
                }
                let normalizedState = status.effectiveState.uppercased()
                if ["FAILED", "CANCELLED", "COMPLETED"].contains(normalizedState) {
                    return false
                }
            }
            if let detail: SpotRunDetail = try? await requestJSON(
                url: baseURL.appending(path: "runs/\(runID)/detail"),
                timeoutInterval: 3
            ) {
                if detail.recovery?.running == true || isActiveRunState(detail.state) {
                    return true
                }
                let normalizedState = detail.state.uppercased()
                if ["FAILED", "CANCELLED", "COMPLETED"].contains(normalizedState) {
                    return false
                }
            }
            try? await Task.sleep(for: .seconds(1))
        }
        return false
    }

    private func applyRunDetail(_ detail: SpotRunDetail) {
        latestRunDetail = detail
        selectedRunID = detail.runID
        pendingReviewCount = detail.reviewSummary?.pendingRows
            ?? detail.processingStats?.reviewRequiredRowsDetected
            ?? 0
        reviewPreviewRows = detail.reviewRowsPreview
        activeArtifacts = detail.artifacts
        signoffDecision = detail.signoff?.decision ?? "accepted"
        signoffNote = detail.signoff?.note ?? ""
        activeRunSummary = SpotRuntimeSummary(
            healthDescription: activeRunSummary.healthDescription,
            reviewPending: pendingReviewCount,
            selectedRunID: detail.runID,
            runState: detail.state,
            runLanguage: detail.language ?? "-",
            reviewMode: detail.reviewMode ?? "-",
            progressDescription: progressDescription(for: detail),
            authenticatedAs: authSummary,
            nextActions: detail.nextActions,
            outputReady: detail.outputReady
        )
    }

    private func applyLightweightRunStatus(baseURL: URL, runID: String) async throws {
        let status: SpotClassifyStatus = try await requestJSON(url: baseURL.appending(path: "classify/status/\(runID)"), timeoutInterval: 2.5)
        let progress = status.progress
        selectedRunID = runID
        latestRunDetail = nil
        pendingReviewCount = selectedOverviewRunSummary?.processingStats?.reviewRequiredRowsDetected
            ?? selectedOverviewRunSummary?.run?.processingStats?.reviewRequiredRowsDetected
            ?? activeRunSummary.reviewPending
        activeRunSummary = SpotRuntimeSummary(
            healthDescription: activeRunSummary.healthDescription,
            reviewPending: pendingReviewCount,
            selectedRunID: runID,
            runState: status.effectiveState,
            runLanguage: activeRunSummary.runLanguage,
            reviewMode: activeRunSummary.reviewMode,
            progressDescription: lightweightProgressDescription(status: status),
            authenticatedAs: authSummary,
            nextActions: [],
            outputReady: false
        )
        if let idx = availableRuns.firstIndex(where: { $0.runID == runID }) {
            availableRuns[idx] = SpotRunRecord(
                runID: runID,
                state: status.effectiveState,
                language: availableRuns[idx].language,
                reviewMode: availableRuns[idx].reviewMode,
                createdAt: availableRuns[idx].createdAt,
                updatedAt: Int(Date().timeIntervalSince1970),
                reviewSummary: availableRuns[idx].reviewSummary,
                progress: progress,
                processingStats: availableRuns[idx].processingStats
            )
        }
    }

    private func primeVisibleRunFromInboxHistory(force: Bool = false) {
        guard let activity = inboxActivities.first(where: {
            guard let runID = $0.runID?.trimmingCharacters(in: .whitespacesAndNewlines), !runID.isEmpty else {
                return false
            }
            return localRunRecord(for: runID) != nil
        }) else {
            return
        }
        guard let runID = activity.runID, !runID.isEmpty else { return }
        if !force && hasVisibleActiveRun {
            return
        }
        let localRecord = localRunRecord(for: runID)
        let resolvedState = localRecord?.state ?? stageBackedRunState(activity.stage)
        let resolvedLanguage = localRecord?.language ?? startLanguage
        let resolvedReviewMode = localRecord?.reviewMode ?? startReviewMode
        selectedRunID = runID
        activeRunSummary = SpotRuntimeSummary(
            healthDescription: activeRunSummary.healthDescription,
            reviewPending: pendingReviewCount,
            selectedRunID: runID,
            runState: resolvedState,
            runLanguage: resolvedLanguage,
            reviewMode: resolvedReviewMode,
            progressDescription: activity.note,
            authenticatedAs: authSummary,
            nextActions: [],
            outputReady: false
        )
        let synthetic = localRecord ?? SpotRunRecord(
            runID: runID,
            state: resolvedState,
            language: resolvedLanguage,
            reviewMode: resolvedReviewMode,
            createdAt: Int(activity.detectedAt),
            updatedAt: Int(activity.updatedAt),
            reviewSummary: nil,
            progress: nil,
            processingStats: nil
        )
        availableRuns = mergeRunRecords(primary: availableRuns, fallback: [synthetic])
    }

    private func fallbackRunsFromLocalState() -> [SpotRunRecord] {
        var records = loadLocalRunRecords()
        let localRunIDs = Set(records.map(\.runID))
        for activity in inboxActivities {
            guard let runID = activity.runID, !runID.isEmpty, !localRunIDs.contains(runID) else { continue }
            guard localRunRecord(for: runID) != nil else { continue }
            records.append(
                SpotRunRecord(
                    runID: runID,
                    state: stageBackedRunState(activity.stage),
                    language: startLanguage,
                    reviewMode: startReviewMode,
                    createdAt: Int(activity.detectedAt),
                    updatedAt: Int(activity.updatedAt),
                    reviewSummary: nil,
                    progress: nil,
                    processingStats: nil
                )
            )
        }
        return records
    }

    private func mergeRunRecords(primary: [SpotRunRecord], fallback: [SpotRunRecord]) -> [SpotRunRecord] {
        var merged: [SpotRunRecord] = []
        var seen: Set<String> = []
        for record in primary + fallback {
            if seen.insert(record.runID).inserted {
                merged.append(record)
            }
        }
        return merged.sorted { lhs, rhs in
            let lhsActive = isActiveRunState(lhs.state)
            let rhsActive = isActiveRunState(rhs.state)
            if lhsActive != rhsActive {
                return lhsActive && !rhsActive
            }
            let lhsCreated = lhs.createdAt ?? 0
            let rhsCreated = rhs.createdAt ?? 0
            if lhsCreated != rhsCreated {
                return lhsCreated > rhsCreated
            }
            return lhs.runID > rhs.runID
        }
    }

    private func stageBackedRunState(_ stage: String) -> String {
        switch stage {
        case "run_started":
            return "STARTING"
        case "waiting_for_run_start":
            return "QUEUED"
        case "failed":
            return "FAILED"
        default:
            return "-"
        }
    }

    private func isActiveRunState(_ state: String?) -> Bool {
        guard let normalized = state?.uppercased() else { return false }
        return ["STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED", "QUEUED"].contains(normalized)
    }

    private func loadLocalRunRecords() -> [SpotRunRecord] {
        let runsURL = URL(fileURLWithPath: nativeConfig.runsDir)
        guard let children = try? FileManager.default.contentsOfDirectory(at: runsURL, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else {
            return []
        }
        return children.compactMap { child in
            guard child.hasDirectoryPath, child.lastPathComponent != "uploads", child.lastPathComponent != "_history" else {
                return nil
            }
            return localRunRecord(for: child.lastPathComponent)
        }
    }

    private func localRunRecord(for runID: String) -> SpotRunRecord? {
        let recordURL = URL(fileURLWithPath: nativeConfig.runsDir).appending(path: runID).appending(path: "run_record.json")
        guard
            let data = try? Data(contentsOf: recordURL),
            let record = try? JSONDecoder().decode(SpotRunRecord.self, from: data)
        else {
            return nil
        }
        return record
    }

    private var selectedRunRecord: SpotRunRecord? {
        availableRuns.first(where: { $0.runID == selectedRunID })
    }

    private var selectedOverviewRunSummary: SpotUploadQueueSummary? {
        operationsOverview?.recentUploads.first(where: { ($0.run?.runID ?? "") == selectedRunID })
    }

    private func loadLocalUploadRecords() -> [SpotUploadRecord] {
        let uploadsURL = URL(fileURLWithPath: nativeConfig.runsDir).appending(path: "uploads")
        guard let children = try? FileManager.default.contentsOfDirectory(at: uploadsURL, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else {
            return []
        }
        return children.compactMap { child in
            guard child.hasDirectoryPath else { return nil }
            let recordURL = child.appending(path: "upload.json")
            guard
                let data = try? Data(contentsOf: recordURL),
                let record = try? JSONDecoder().decode(SpotUploadRecord.self, from: data)
            else {
                return nil
            }
            return record
        }
        .sorted { $0.uploadID > $1.uploadID }
    }

    private func loadReviewQueue(for runID: String) async throws {
        guard let baseURL else { return }
        let queue: SpotReviewQueue = try await requestJSON(url: baseURL.appending(path: "runs/\(runID)/review-rows"))
        reviewQueueRows = queue.rows
        if let rowIndex = selectedReviewRowIndex, queue.rows.contains(where: { $0.rowIndex == rowIndex }) {
            try await loadReviewInspectorSync(rowIndex: rowIndex)
        } else if let first = queue.rows.first {
            try await loadReviewInspectorSync(rowIndex: first.rowIndex)
        } else {
            selectedReviewRowIndex = nil
            activeReviewInspector = nil
            reviewDraft = .empty
        }
    }

    private func loadReviewInspectorSync(rowIndex: Int) async throws {
        guard let baseURL, !selectedRunID.isEmpty else { return }
        let inspector: SpotReviewRowInspector = try await requestJSON(
            url: baseURL.appending(path: "runs/\(selectedRunID)/review-rows/\(rowIndex)")
        )
        selectedReviewRowIndex = rowIndex
        activeReviewInspector = inspector
        reviewDraft = SpotReviewDraft(
            reviewState: inspector.reviewControls.reviewState,
            reviewDecision: inspector.reviewControls.reviewDecision ?? "",
            reviewerNote: inspector.reviewControls.reviewerNote
        )
    }

    private func mergeUpdatedReviewRow(_ row: SpotReviewRowPreview) {
        if let previewIndex = reviewPreviewRows.firstIndex(where: { $0.rowIndex == row.rowIndex }) {
            reviewPreviewRows[previewIndex] = row
        }
        if let queueIndex = reviewQueueRows.firstIndex(where: { $0.rowIndex == row.rowIndex }) {
            reviewQueueRows[queueIndex] = row
        }
    }

    private func average(of values: [Double]) -> Double? {
        guard !values.isEmpty else { return nil }
        return values.reduce(0, +) / Double(values.count)
    }

    private func parseStatsUpdatedAt(_ stats: SpotProcessingStats?) -> Date? {
        guard let raw = stats?.updatedAt?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else {
            return nil
        }
        return ISO8601DateFormatter().date(from: raw)
    }

    private func progressDescription(for detail: SpotRunDetail) -> String {
        guard let progress = detail.progress else {
            return "No progress payload available for this run."
        }
        let processed = progress.processedRows.map(String.init) ?? "-"
        let total = progress.totalRows.map(String.init) ?? "-"
        let percentage = progress.progressPercentage.map { String(format: "%.1f%%", $0) } ?? "-"
        let state = progress.state ?? detail.state
        let message = progress.message?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let message, !message.isEmpty {
            return "\(state) · \(processed)/\(total) rows · \(percentage) · \(message)"
        }
        return "\(state) · \(processed)/\(total) rows · \(percentage)"
    }

    private func lightweightProgressDescription(status: SpotClassifyStatus) -> String {
        guard let progress = status.progress else {
            return status.effectiveState
        }
        let processed = progress.processedRows.map(String.init) ?? "-"
        let total = progress.totalRows.map(String.init) ?? "-"
        let percentage = progress.progressPercentage.map { String(format: "%.1f%%", $0) } ?? "-"
        let message = progress.message?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let message, !message.isEmpty {
            return "\(status.effectiveState) · \(processed)/\(total) rows · \(percentage) · \(message)"
        }
        return "\(status.effectiveState) · \(processed)/\(total) rows · \(percentage)"
    }

    private func fallbackRuns(from overview: SpotOperationsOverview?) -> [SpotRunRecord] {
        guard let overview else { return [] }
        return overview.recentUploads.compactMap { summary in
            guard let run = summary.run, let runID = run.runID else { return nil }
            return SpotRunRecord(
                runID: runID,
                state: run.state,
                language: nil,
                reviewMode: nil,
                createdAt: nil,
                updatedAt: nil,
                reviewSummary: SpotRunReviewSummary(
                    reviewRequiredRows: summary.processingStats?.reviewRequiredRowsDetected ?? 0,
                    reviewedRows: 0,
                    pendingRows: summary.processingStats?.reviewRequiredRowsDetected ?? 0
                ),
                progress: SpotRunProgress(
                    state: run.state,
                    message: nil,
                    totalRows: run.totalRows,
                    processedRows: run.processedRows,
                    progressPercentage: run.progressPercentage ?? run.rowProgressPercentage,
                    startedAt: nil,
                    completedAt: nil
                ),
                processingStats: summary.processingStats ?? run.processingStats
            )
        }
    }

    private func suggestedRunID() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return "run-\(formatter.string(from: Date()))"
    }

    private func resolveBundledLauncher() -> URL? {
        Bundle.main.bundleURL
            .appending(path: "Contents")
            .appending(path: "Resources")
            .appending(path: "spot-core")
            .appending(path: "bin")
            .appending(path: "launch-bundled-appliance.sh")
    }

    private func bundledCoreRootURL() -> URL? {
        let root = Bundle.main.bundleURL
            .appending(path: "Contents")
            .appending(path: "Resources")
            .appending(path: "spot-core")
        return FileManager.default.fileExists(atPath: root.path) ? root : nil
    }

    var spotDataHome: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Library")
            .appending(path: "Application Support")
            .appending(path: "spot")
    }

    var spotLogHome: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Library")
            .appending(path: "Logs")
            .appending(path: "spot")
    }

    var defaultIntakeInboxURL: URL {
        spotDataHome.appending(path: "intake").appending(path: "incoming")
    }

    var defaultIntakeProcessedURL: URL {
        spotDataHome.appending(path: "intake").appending(path: "processed")
    }

    var defaultIntakeFailedURL: URL {
        spotDataHome.appending(path: "intake").appending(path: "failed")
    }

    private var nativeConfigURL: URL {
        spotDataHome.appending(path: "native-runtime.env")
    }

    private var nativeConfigDatabaseURL: URL {
        spotDataHome.appending(path: "native-config.sqlite3")
    }

    private var inboxActivityURL: URL {
        spotDataHome.appending(path: "inbox-activity.json")
    }

    private func ensureSupportDirectories() {
        try? FileManager.default.createDirectory(at: spotDataHome, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? FileManager.default.createDirectory(at: spotLogHome, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? FileManager.default.createDirectory(at: defaultIntakeInboxURL, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? FileManager.default.createDirectory(at: defaultIntakeProcessedURL, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? FileManager.default.createDirectory(at: defaultIntakeFailedURL, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    }

    private var supervisorLogURL: URL {
        spotLogHome.appending(path: "native-app.log")
    }

    private func appendSupervisorLog(_ message: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let line = "[\(timestamp)] \(message)\n"
        do {
            if !FileManager.default.fileExists(atPath: supervisorLogURL.path) {
                try line.write(to: supervisorLogURL, atomically: true, encoding: .utf8)
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: supervisorLogURL.path)
                return
            }
            let handle = try FileHandle(forWritingTo: supervisorLogURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            handle.write(Data(line.utf8))
        } catch {
            // Keep supervisor logging best-effort only.
        }
    }

    private func ensureNativeConfigFile(forceRewrite: Bool = false) {
        let url = nativeConfigURL
        if !forceRewrite, FileManager.default.fileExists(atPath: url.path) {
            return
        }
        let template = nativeConfigTemplate()
        do {
            try template.write(to: url, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
        } catch {
            appendLog("Could not write native config template: \(error.localizedDescription)")
        }
    }

    private func nativeConfigTemplate() -> String {
        let defaultRuns = spotDataHome.appending(path: "runs").path
        let defaultLogs = spotLogHome.path
        let bundledSSOT = bundledCoreRootURL()?.appending(path: "ssot/ssot.json").path ?? ""
        let suggestedPython = ProcessInfo.processInfo.environment["SPOT_NATIVE_PYTHON_BIN"] ?? ""
        return """
        # {spot} native runtime configuration
        # Fill in SPOT_NATIVE_PYTHON_BIN with an executable Python from your local machine.
        # Example: /Users/your-user/Projects/spot/.venv/bin/python
        SPOT_NATIVE_PYTHON_BIN="\(suggestedPython)"
        SPOT_NATIVE_RUNS_DIR="\(defaultRuns)"
        SPOT_NATIVE_LOGS_DIR="\(defaultLogs)"
        SPOT_LOCKED_SSOT_PATH="\(bundledSSOT)"
        SPOT_NATIVE_PORT="8765"
        SPOT_NATIVE_INTAKE_WATCH_DIR="\(defaultIntakeInboxURL.path)"
        SPOT_NATIVE_INTAKE_ARCHIVE_DIR="\(defaultIntakeProcessedURL.path)"
        SPOT_NATIVE_INTAKE_FAILED_DIR="\(defaultIntakeFailedURL.path)"
        SPOT_NATIVE_AUTO_START_WATCH_FOLDER="1"
        # Set a non-default local access code before real operator use.
        SPOT_LOCAL_ACCESS_CODE=""
        """
    }

    private func loadNativeConfigFromEnv() -> SpotNativeConfig {
        var config = SpotNativeConfig.empty
        let url = nativeConfigURL
        guard let content = try? String(contentsOf: url, encoding: .utf8) else {
            return config
        }
        for rawLine in content.split(separator: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !line.isEmpty, !line.hasPrefix("#"), let idx = line.firstIndex(of: "=") else { continue }
            let key = String(line[..<idx])
            let rawValue = String(line[line.index(after: idx)...])
            let value = rawValue.trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
            switch key {
            case "SPOT_NATIVE_PYTHON_BIN":
                config.pythonBin = value
            case "SPOT_NATIVE_RUNS_DIR":
                config.runsDir = value
            case "SPOT_NATIVE_LOGS_DIR":
                config.logsDir = value
            case "SPOT_LOCAL_ACCESS_CODE":
                config.accessCode = value
            case "SPOT_LOCKED_SSOT_PATH":
                config.lockedSSOTPath = value
            case "SPOT_NATIVE_PORT":
                config.port = Int(value) ?? 8765
            case "SPOT_NATIVE_INTAKE_WATCH_DIR":
                config.intakeWatchDir = value
            case "SPOT_NATIVE_INTAKE_ARCHIVE_DIR":
                config.intakeArchiveDir = value
            case "SPOT_NATIVE_INTAKE_FAILED_DIR":
                config.intakeFailedDir = value
            case "SPOT_NATIVE_AUTO_START_WATCH_FOLDER":
                config.autoStartWatchFolder = !["0", "false", "no"].contains(value.lowercased())
            default:
                continue
            }
        }
        return config
    }

    private func loadNativeConfig() -> SpotNativeConfig {
        let envConfig = loadNativeConfigFromEnv()
        let dbConfig = loadNativeConfigFromDatabase() ?? .empty
        let merged = mergedNativeConfig(primary: dbConfig, fallback: envConfig)
        if loadNativeConfigFromDatabase() == nil, nativeConfigHasMeaningfulValues(envConfig) {
            saveNativeConfigToDatabase(envConfig)
        }
        return merged
    }

    private func loadInboxActivities() -> [SpotInboxDocumentActivity] {
        guard let data = try? Data(contentsOf: inboxActivityURL) else { return [] }
        let decoder = JSONDecoder()
        return (try? decoder.decode([SpotInboxDocumentActivity].self, from: data)) ?? []
    }

    private func saveInboxActivities() {
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(inboxActivities)
            try data.write(to: inboxActivityURL, options: [.atomic])
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: inboxActivityURL.path)
        } catch {
            appendLog("Could not save inbox activities: \(error.localizedDescription)")
        }
    }

    private func saveNativeConfig() {
        saveNativeConfigToDatabase(nativeConfig)
        saveNativeConfigToEnv()
    }

    private func saveNativeConfigToEnv() {
        let boolValue = nativeConfig.autoStartWatchFolder ? "1" : "0"
        let content = """
        # {spot} native runtime configuration
        # Fill in SPOT_NATIVE_PYTHON_BIN with an executable Python from your local machine.
        # Example: /Users/your-user/Projects/spot/.venv/bin/python
        SPOT_NATIVE_PYTHON_BIN="\(nativeConfig.pythonBin)"
        SPOT_NATIVE_RUNS_DIR="\(nativeConfig.runsDir)"
        SPOT_NATIVE_LOGS_DIR="\(nativeConfig.logsDir)"
        SPOT_LOCKED_SSOT_PATH="\(nativeConfig.lockedSSOTPath)"
        SPOT_NATIVE_PORT="\(nativeConfig.port)"
        SPOT_NATIVE_INTAKE_WATCH_DIR="\(nativeConfig.intakeWatchDir)"
        SPOT_NATIVE_INTAKE_ARCHIVE_DIR="\(nativeConfig.intakeArchiveDir)"
        SPOT_NATIVE_INTAKE_FAILED_DIR="\(nativeConfig.intakeFailedDir)"
        SPOT_NATIVE_AUTO_START_WATCH_FOLDER="\(boolValue)"
        SPOT_LOCAL_ACCESS_CODE="\(nativeConfig.accessCode)"
        """
        do {
            try content.write(to: nativeConfigURL, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: nativeConfigURL.path)
        } catch {
            appendLog("Could not save native config: \(error.localizedDescription)")
        }
    }

    private func mergedNativeConfig(primary: SpotNativeConfig, fallback: SpotNativeConfig) -> SpotNativeConfig {
        SpotNativeConfig(
            pythonBin: primary.pythonBin.isEmpty ? fallback.pythonBin : primary.pythonBin,
            runsDir: primary.runsDir.isEmpty ? fallback.runsDir : primary.runsDir,
            logsDir: primary.logsDir.isEmpty ? fallback.logsDir : primary.logsDir,
            accessCode: primary.accessCode.isEmpty ? fallback.accessCode : primary.accessCode,
            lockedSSOTPath: primary.lockedSSOTPath.isEmpty ? fallback.lockedSSOTPath : primary.lockedSSOTPath,
            port: primary.port == 0 ? fallback.port : primary.port,
            intakeWatchDir: primary.intakeWatchDir.isEmpty ? fallback.intakeWatchDir : primary.intakeWatchDir,
            intakeArchiveDir: primary.intakeArchiveDir.isEmpty ? fallback.intakeArchiveDir : primary.intakeArchiveDir,
            intakeFailedDir: primary.intakeFailedDir.isEmpty ? fallback.intakeFailedDir : primary.intakeFailedDir,
            autoStartWatchFolder: primary.autoStartWatchFolder
        )
    }

    private func nativeConfigHasMeaningfulValues(_ config: SpotNativeConfig) -> Bool {
        !config.pythonBin.isEmpty ||
        !config.runsDir.isEmpty ||
        !config.logsDir.isEmpty ||
        !config.accessCode.isEmpty ||
        !config.lockedSSOTPath.isEmpty ||
        !config.intakeWatchDir.isEmpty ||
        !config.intakeArchiveDir.isEmpty ||
        !config.intakeFailedDir.isEmpty
    }

    private func loadNativeConfigFromDatabase() -> SpotNativeConfig? {
        var db: OpaquePointer?
        guard sqlite3_open(nativeConfigDatabaseURL.path, &db) == SQLITE_OK, let db else {
            sqlite3_close(db)
            return nil
        }
        defer { sqlite3_close(db) }

        let createSQL = """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
        """
        guard sqlite3_exec(db, createSQL, nil, nil, nil) == SQLITE_OK else {
            return nil
        }

        let query = "SELECT key, value FROM app_settings"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, query, -1, &statement, nil) == SQLITE_OK, let statement else {
            sqlite3_finalize(statement)
            return nil
        }
        defer { sqlite3_finalize(statement) }

        var config = SpotNativeConfig.empty
        var sawRow = false
        while sqlite3_step(statement) == SQLITE_ROW {
            sawRow = true
            guard
                let keyCString = sqlite3_column_text(statement, 0),
                let valueCString = sqlite3_column_text(statement, 1)
            else { continue }
            let key = String(cString: keyCString)
            let value = String(cString: valueCString)
            switch key {
            case "python_bin":
                config.pythonBin = value
            case "runs_dir":
                config.runsDir = value
            case "logs_dir":
                config.logsDir = value
            case "access_code":
                config.accessCode = value
            case "locked_ssot_path":
                config.lockedSSOTPath = value
            case "port":
                config.port = Int(value) ?? config.port
            case "intake_watch_dir":
                config.intakeWatchDir = value
            case "intake_archive_dir":
                config.intakeArchiveDir = value
            case "intake_failed_dir":
                config.intakeFailedDir = value
            case "auto_start_watch_folder":
                config.autoStartWatchFolder = !["0", "false", "no"].contains(value.lowercased())
            default:
                continue
            }
        }
        return sawRow ? config : nil
    }

    private func saveNativeConfigToDatabase(_ config: SpotNativeConfig) {
        var db: OpaquePointer?
        guard sqlite3_open(nativeConfigDatabaseURL.path, &db) == SQLITE_OK, let db else {
            sqlite3_close(db)
            appendLog("Could not open native config database.")
            return
        }
        defer { sqlite3_close(db) }

        let createSQL = """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
        """
        guard sqlite3_exec(db, createSQL, nil, nil, nil) == SQLITE_OK else {
            appendLog("Could not initialize native config database.")
            return
        }

        let insertSQL = """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, insertSQL, -1, &statement, nil) == SQLITE_OK, let statement else {
            sqlite3_finalize(statement)
            appendLog("Could not prepare native config database write.")
            return
        }
        defer { sqlite3_finalize(statement) }

        let now = Int(Date().timeIntervalSince1970)
        let rows: [(String, String)] = [
            ("python_bin", config.pythonBin),
            ("runs_dir", config.runsDir),
            ("logs_dir", config.logsDir),
            ("access_code", config.accessCode),
            ("locked_ssot_path", config.lockedSSOTPath),
            ("port", String(config.port)),
            ("intake_watch_dir", config.intakeWatchDir),
            ("intake_archive_dir", config.intakeArchiveDir),
            ("intake_failed_dir", config.intakeFailedDir),
            ("auto_start_watch_folder", config.autoStartWatchFolder ? "1" : "0"),
        ]

        for (key, value) in rows {
            sqlite3_reset(statement)
            sqlite3_clear_bindings(statement)
            sqlite3_bind_text(statement, 1, key, -1, SQLITE_TRANSIENT)
            sqlite3_bind_text(statement, 2, value, -1, SQLITE_TRANSIENT)
            sqlite3_bind_int64(statement, 3, sqlite3_int64(now))
            guard sqlite3_step(statement) == SQLITE_DONE else {
                appendLog("Could not persist native config key \(key) to database.")
                return
            }
        }
    }
}
