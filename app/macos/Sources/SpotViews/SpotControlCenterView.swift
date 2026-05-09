import AppKit
import SwiftUI

struct SpotControlCenterView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Control Center")
                .font(.title2)
                .fontWeight(.semibold)

            GroupBox("Runtime Controls") {
                HStack {
                    Button("Refresh Status") {
                        Task { await service.refreshRuntimeSnapshot() }
                    }
                    Button("Run Security Check") {
                        Task { await service.validatePreflightSecurity() }
                    }
                    Button("Open Native Config") { service.openNativeConfig() }
                    Button("Rewrite Config Template") { service.rewriteNativeConfigTemplate() }
                    Button("Open Runs Directory") { service.openRunsDirectory() }
                    Button("Open Logs") { service.openLogs() }
                    Button("Open Intake") {
                        service.navigate(to: .intake)
                    }
                    Button("Open Operations") {
                        service.navigate(to: .operations)
                    }
                    Button("Open Native Review") {
                        service.navigate(to: .review)
                    }
                    .disabled(service.selectedRunID.isEmpty)
                }
            }

            GroupBox("Current Summary") {
                VStack(alignment: .leading, spacing: 8) {
                    Text(service.activeRunSummary.healthDescription)
                    Text("Mode: native local")
                        .foregroundStyle(.secondary)
                    Text("Selected Run: \(service.activeRunSummary.selectedRunID.isEmpty ? "-" : service.activeRunSummary.selectedRunID)")
                    Text("Run State: \(service.activeRunSummary.runState)")
                    Text("Progress: \(service.activeRunSummary.progressDescription)")
                    Text("Pending Review: \(service.activeRunSummary.reviewPending)")
                    if !service.activeRunSummary.nextActions.isEmpty {
                        Text("Next Actions: \(service.activeRunSummary.nextActions.joined(separator: ", "))")
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            Spacer()
        }
        .padding(24)
        .frame(minWidth: 760, minHeight: 520)
    }
}
