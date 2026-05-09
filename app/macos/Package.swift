// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "spot-macos",
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
