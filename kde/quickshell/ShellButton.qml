// Inline hit targets avoid tooltip popups intercepting Dock clicks on Wayland.
import QtQuick

Item {
    id: control
    signal clicked
    property string text: ""
    readonly property bool hovered: mouse.containsMouse
    readonly property bool down: mouse.pressed
    property bool selected: false
    property string hint: text
    Accessible.role: Accessible.Button
    Accessible.name: hint
    property url imageSource: ""
    implicitHeight: 36
    implicitWidth: Math.max(36, label.implicitWidth + 24 + (imageSource.toString() ? 28 : 0))
    Rectangle {
        anchors.fill: parent
        radius: 10
        color: control.down ? "#354960" : control.selected ? "#283e50" : control.hovered ? "#263343" : "transparent"
        border.width: control.selected ? 1 : 0
        border.color: "#5eb7c4"
    }
    Item {
        anchors.fill: parent
        anchors.margins: 10
        Image {
            id: icon
            visible: control.imageSource.toString().length > 0
            source: control.imageSource
            width: 24
            height: 24
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            fillMode: Image.PreserveAspectFit
        }
        Text {
            id: label
            anchors.left: icon.visible ? icon.right : parent.left
            anchors.leftMargin: icon.visible ? 8 : 0
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            textFormat: Text.PlainText
            color: control.selected ? "#bcecf1" : "#dce3ec"
            font.family: "Noto Sans"
            font.pixelSize: 13
            elide: Text.ElideRight
            horizontalAlignment: icon.visible ? Text.AlignLeft : Text.AlignHCenter
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: control.clicked()
    }
}
