// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "spot-app",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(name: "spot", targets: ["spotshell"])
    ],
    targets: [
        .executableTarget(
            name: "spotshell",
            path: "Sources"
        )
    ]
)
