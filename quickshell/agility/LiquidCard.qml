import QtQuick

Item {
    id: root

    // Sizing & Appearance properties
    property real radius: 32
    property bool isTile: false // Set to true for inner sub-cards / sub-tiles
    property color dropletColorTop: Theme.isGlass ? "#38141F2E" : Theme.colBg
    property color dropletColorBottom: Theme.isGlass ? "#550A1118" : Theme.colBg
    property color rimColor: Theme.isGlass ? "#26FFFFFF" : Theme.borderColor
    property real rimWidth: Theme.isGlass ? 1.0 : Theme.borderWidth

    // Direct content container
    default property alias content: contentContainer.children
    property alias contentItem: contentContainer

    // ─── 1. Soft Ambient Drop Shadow (Elevation off wallpaper) ───
    Rectangle {
        anchors.fill: parent
        anchors.topMargin: root.isTile ? 1 : 4
        anchors.bottomMargin: root.isTile ? -1 : -4
        anchors.leftMargin: root.isTile ? 0 : 2
        anchors.rightMargin: root.isTile ? 0 : 2
        radius: root.radius
        color: Theme.isGlass ? "#38000000" : (Theme.isOled ? "transparent" : "#1A000000")
        visible: !root.isTile
        z: 0
    }

    // ─── 2. Liquid Glass Body (Smooth Vertical Translucency Gradient) ───
    Rectangle {
        id: dropletBody
        anchors.fill: parent
        radius: root.radius
        antialiasing: true
        z: 1

        color: Theme.isGlass ? "transparent" : (root.isTile ? Theme.colBgTile : Theme.colBg)

        gradient: Theme.isGlass ? liquidGradient : null

        Gradient {
            id: liquidGradient
            GradientStop {
                position: 0.0
                color: root.isTile ? "#321C2A38" : root.dropletColorTop
            }
            GradientStop {
                position: 0.55
                color: root.isTile ? "#4216222E" : Qt.rgba(root.dropletColorBottom.r * 1.1, root.dropletColorBottom.g * 1.1, root.dropletColorBottom.b * 1.1, root.dropletColorBottom.a * 0.85)
            }
            GradientStop {
                position: 1.0
                color: root.isTile ? "#4E121B24" : root.dropletColorBottom
            }
        }

        border.color: root.rimColor
        border.width: root.rimWidth

        // ─── 3. Curved Specular Dome Sheen (Convex Meniscus Highlight) ───
        // Curved organic highlight that hugs the top rounded dome and softly fades out
        Rectangle {
            id: specularDome
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 1
            width: Math.max(0, parent.width - 4)
            height: Math.min(parent.height * 0.45, Math.max(16, root.radius * 1.35))
            radius: Math.max(1, root.radius - 2)
            antialiasing: true
            visible: Theme.isGlass

            gradient: Gradient {
                GradientStop { position: 0.0; color: root.isTile ? "#22FFFFFF" : "#38FFFFFF" }
                GradientStop { position: 0.4; color: root.isTile ? "#0EFFFFFF" : "#14FFFFFF" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // ─── 4. Caustic Bottom Bounce Rim (Refracted Light at Base) ───
        Rectangle {
            id: causticRim
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottomMargin: 1
            width: Math.max(0, parent.width - root.radius)
            height: Math.min(7, root.radius * 0.35)
            radius: root.radius
            antialiasing: true
            visible: Theme.isGlass && !root.isTile

            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 1.0; color: "#187DD3FC" }
            }
        }

        // ─── 5. Content Container ───
        Item {
            id: contentContainer
            anchors.fill: parent
            z: 2
        }
    }
}
