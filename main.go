package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const (
	BoardSize = 15
)

type MessageType string

const (
	MsgJoin       MessageType = "join"
	MsgJoined     MessageType = "joined"
	MsgMove       MessageType = "move"
	MsgMoved      MessageType = "moved"
	MsgState      MessageType = "state"
	MsgResult     MessageType = "result"
	MsgReconnect  MessageType = "reconnect"
	MsgError      MessageType = "error"
	MsgRoomList   MessageType = "room_list"
	MsgCreateRoom MessageType = "create_room"
	MsgHeartbeat  MessageType = "heartbeat"
)

type Message struct {
	Type      MessageType `json:"type"`
	RoomID    string      `json:"room_id,omitempty"`
	RoomCode  string      `json:"room_code,omitempty"`
	Player    int         `json:"player,omitempty"`
	PlayerID  string      `json:"player_id,omitempty"`
	Move      *MoveData   `json:"move,omitempty"`
	Board     [][]int     `json:"board,omitempty"`
	Turn      int         `json:"turn,omitempty"`
	Winner    int         `json:"winner,omitempty"`
	Seq       int64       `json:"seq,omitempty"`
	Message   string      `json:"message,omitempty"`
	Rooms     []RoomInfo  `json:"rooms,omitempty"`
}

type MoveData struct {
	Row int `json:"row"`
	Col int `json:"col"`
}

type RoomInfo struct {
	ID       string `json:"id"`
	Code     string `json:"code"`
	Name     string `json:"name"`
	Players  int    `json:"players"`
	MaxPlayers int  `json:"max_players"`
	Status   string `json:"status"`
}

type Room struct {
	ID          string
	Code        string
	Name        string
	Board       [][]int
	Players     map[string]*Player
	Turn        int
	Status      string
	Seq         int64
	LastMove    *MoveData
	Moves       []MoveRecord
	mu          sync.Mutex
}

type MoveRecord struct {
	Player int `json:"player"`
	Row    int `json:"row"`
	Col    int `json:"col"`
}

type Player struct {
	ID     string
	Conn   *websocket.Conn
	Player int
	Room   *Room
}

var (
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool {
			return true
		},
		ReadBufferSize:  1024,
		WriteBufferSize: 1024,
	}

	rooms      = make(map[string]*Room)
	codeToRoom = make(map[string]string)
	players    = make(map[string]*Player)
	roomsMu    sync.RWMutex
	playerMu   sync.RWMutex
)

func main() {
	http.HandleFunc("/ws", handleWebSocket)
	http.HandleFunc("/api/rooms", handleRooms)

	addr := ":8080"
	log.Printf("Gomoku Online Server starting on %s", addr)
	log.Printf("WebSocket: ws://localhost%s/ws", addr)
	log.Printf("REST API: http://localhost%s/api/rooms", addr)

	go cleanupEmptyRooms()
	go generateRoomCodes()

	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func generateRoomCodes() {
	rand.Seed(time.Now().UnixNano())
}

func generateRoomCode() string {
	code := fmt.Sprintf("%06d", rand.Intn(1000000))
	return code
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade failed: %v", err)
		return
	}
	defer conn.Close()

	playerID := fmt.Sprintf("p%d", time.Now().UnixNano())
	player := &Player{
		ID:   playerID,
		Conn: conn,
	}

	playerMu.Lock()
	players[playerID] = player
	playerMu.Unlock()

	sendMessage(conn, Message{
		Type:     MsgJoined,
		PlayerID: playerID,
		Message:  "Connected",
	})

	log.Printf("Player connected: %s", playerID)

	done := make(chan struct{})
	go pingLoop(conn, done)

	for {
		var msg Message
		err := conn.ReadJSON(&msg)
		if err != nil {
			log.Printf("Player %s disconnected: %v", playerID, err)
			close(done)
			handleDisconnect(player)
			break
		}

		processMessage(player, &msg)
	}
}

func pingLoop(conn *websocket.Conn, done chan struct{}) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			err := conn.WriteJSON(Message{
				Type: MsgHeartbeat,
				Seq:  time.Now().UnixMilli(),
			})
			if err != nil {
				return
			}
		case <-done:
			return
		}
	}
}

func handleDisconnect(player *Player) {
	playerMu.Lock()
	delete(players, player.ID)
	playerMu.Unlock()

	if player.Room != nil {
		room := player.Room
		room.mu.Lock()
		delete(room.Players, player.ID)
		room.mu.Unlock()

		if len(room.Players) == 0 {
			roomsMu.Lock()
			delete(rooms, room.ID)
			delete(codeToRoom, room.Code)
			roomsMu.Unlock()
			log.Printf("Room %s (%s) deleted - no players", room.ID, room.Code)
		} else {
			broadcastRoomState(room)
		}

		log.Printf("Player %s left room %s (code: %s)", player.ID, room.ID, room.Code)
	}
}

func processMessage(player *Player, msg *Message) {
	switch msg.Type {
	case MsgCreateRoom:
		handleCreateRoom(player, msg)
	case MsgJoin:
		handleJoinRoom(player, msg)
	case MsgMove:
		handleMove(player, msg)
	case MsgReconnect:
		handleReconnect(player, msg)
	case MsgRoomList:
		handleGetRooms(player)
	default:
		sendError(player.Conn, "Unknown message type")
	}
}

func handleCreateRoom(player *Player, msg *Message) {
	roomsMu.Lock()

	roomID := fmt.Sprintf("r%d", time.Now().UnixNano())
	code := generateRoomCode()

	for {
		if _, exists := codeToRoom[code]; !exists {
			break
		}
		code = generateRoomCode()
	}

	board := make([][]int, BoardSize)
	for i := range board {
		board[i] = make([]int, BoardSize)
	}

	room := &Room{
		ID:      roomID,
		Code:    code,
		Name:    msg.Message,
		Board:   board,
		Players: make(map[string]*Player),
		Turn:    1,
		Status:  "waiting",
		Moves:   []MoveRecord{},
	}

	rooms[roomID] = room
	codeToRoom[code] = roomID
	roomsMu.Unlock()

	player.Room = room
	player.Player = 1

	room.mu.Lock()
	room.Players[player.ID] = player
	room.mu.Unlock()

	sendMessage(player.Conn, Message{
		Type:     MsgJoined,
		RoomID:   roomID,
		RoomCode: code,
		Player:   1,
		Board:    room.Board,
		Turn:     room.Turn,
		Message:  "Room created",
	})

	log.Printf("Room %s (code: %s) created by %s", roomID, code, player.ID)
}

func handleJoinRoom(player *Player, msg *Message) {
	var roomID string
	var exists bool

	roomsMu.RLock()
	if msg.RoomCode != "" {
		roomID, exists = codeToRoom[msg.RoomCode]
	} else if msg.RoomID != "" {
		roomID = msg.RoomID
		exists = true
	}
	roomsMu.RUnlock()

	if !exists {
		sendError(player.Conn, "Room code invalid or room not found")
		return
	}

	roomsMu.RLock()
	room, ok := rooms[roomID]
	roomsMu.RUnlock()

	if !ok {
		sendError(player.Conn, "Room not found")
		return
	}

	room.mu.Lock()
	defer room.mu.Unlock()

	if room.Status == "finished" {
		sendError(player.Conn, "Room game is already finished")
		return
	}

	if len(room.Players) >= 2 {
		sendError(player.Conn, "Room is full")
		return
	}

	player.Room = room
	player.Player = 2
	room.Players[player.ID] = player

	if len(room.Players) == 2 {
		room.Status = "playing"
	}

	sendMessage(player.Conn, Message{
		Type:     MsgJoined,
		RoomID:   room.ID,
		RoomCode: room.Code,
		Player:   2,
		Board:    room.Board,
		Turn:     room.Turn,
		Message:  "Joined room",
	})

	broadcastRoomState(room)

	log.Printf("Player %s joined room %s (code: %s)", player.ID, room.ID, room.Code)
}

func handleMove(player *Player, msg *Message) {
	if player.Room == nil {
		sendError(player.Conn, "Not in a room")
		return
	}

	room := player.Room
	room.mu.Lock()
	defer room.mu.Unlock()

	if room.Status != "playing" {
		sendError(player.Conn, "Game not in progress")
		return
	}

	if room.Turn != player.Player {
		sendError(player.Conn, "Not your turn")
		return
	}

	if msg.Move == nil {
		sendError(player.Conn, "Invalid move")
		return
	}

	r, c := msg.Move.Row, msg.Move.Col
	if r < 0 || r >= BoardSize || c < 0 || c >= BoardSize {
		sendError(player.Conn, "Move out of bounds")
		return
	}

	if room.Board[r][c] != 0 {
		sendError(player.Conn, "Position already occupied")
		return
	}

	room.Board[r][c] = player.Player
	room.LastMove = msg.Move
	room.Moves = append(room.Moves, MoveRecord{
		Player: player.Player,
		Row:    r,
		Col:    c,
	})

	if checkWin(room.Board, r, c, player.Player) {
		room.Status = "finished"
		room.Seq++
		seq := room.Seq

		for _, p := range room.Players {
			sendMessage(p.Conn, Message{
				Type:   MsgResult,
				RoomID: room.ID,
				Board:  room.Board,
				Winner: player.Player,
				Seq:    seq,
			})
		}
		return
	}

	if room.Turn == 1 {
		room.Turn = 2
	} else {
		room.Turn = 1
	}
	room.Seq++
	seq := room.Seq

	for _, p := range room.Players {
		sendMessage(p.Conn, Message{
			Type:   MsgMoved,
			RoomID: room.ID,
			Player: player.Player,
			Move:   msg.Move,
			Board:  room.Board,
			Turn:   room.Turn,
			Seq:    seq,
		})
	}
}

func handleReconnect(player *Player, msg *Message) {
	roomsMu.RLock()
	room, exists := rooms[msg.RoomID]
	roomsMu.RUnlock()

	if !exists {
		sendError(player.Conn, "Room not found")
		return
	}

	room.mu.Lock()
	defer room.mu.Unlock()

	originalPlayer, wasPlayer := room.Players[msg.PlayerID]
	if !wasPlayer {
		sendError(player.Conn, "Not authorized - invalid player ID")
		return
	}

	delete(room.Players, msg.PlayerID)
	player.Room = room
	player.Player = originalPlayer.Player
	room.Players[player.ID] = player

	sendMessage(player.Conn, Message{
		Type:     MsgState,
		RoomID:   room.ID,
		RoomCode: room.Code,
		Player:   player.Player,
		Board:    room.Board,
		Turn:     room.Turn,
		Seq:      room.Seq,
		Message:  "Reconnected",
	})

	log.Printf("Player %s reconnected to room %s", player.ID, room.ID)
}

func handleGetRooms(player *Player) {
	roomsMu.RLock()
	defer roomsMu.RUnlock()

	var roomList []RoomInfo
	for _, room := range rooms {
		if room.Status == "waiting" {
			roomList = append(roomList, RoomInfo{
				ID:         room.ID,
				Code:       room.Code,
				Name:       room.Name,
				Players:    len(room.Players),
				MaxPlayers: 2,
				Status:     room.Status,
			})
		}
	}

	sendMessage(player.Conn, Message{
		Type:  MsgRoomList,
		Rooms: roomList,
	})
}

func handleRooms(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	roomsMu.RLock()
	var roomList []RoomInfo
	for _, room := range rooms {
		roomList = append(roomList, RoomInfo{
			ID:         room.ID,
			Code:       room.Code,
			Name:       room.Name,
			Players:    len(room.Players),
			MaxPlayers: 2,
			Status:     room.Status,
		})
	}
	roomsMu.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(roomList)
}

func broadcastRoomState(room *Room) {
	for _, p := range room.Players {
		sendMessage(p.Conn, Message{
			Type:     MsgState,
			RoomID:   room.ID,
			RoomCode: room.Code,
			Board:    room.Board,
			Turn:     room.Turn,
		})
	}
}

func sendMessage(conn *websocket.Conn, msg Message) {
	err := conn.WriteJSON(msg)
	if err != nil {
		log.Printf("Error sending message: %v", err)
	}
}

func sendError(conn *websocket.Conn, errMsg string) {
	sendMessage(conn, Message{
		Type:    MsgError,
		Message: errMsg,
	})
}

func checkWin(board [][]int, row, col, player int) bool {
	directions := [][2]int{{0, 1}, {1, 0}, {1, 1}, {1, -1}}

	for _, dir := range directions {
		count := 1
		dx, dy := dir[0], dir[1]

		r, c := row+dx, col+dy
		for r >= 0 && r < BoardSize && c >= 0 && c < BoardSize && board[r][c] == player {
			count++
			r += dx
			c += dy
		}

		r, c = row-dx, col-dy
		for r >= 0 && r < BoardSize && c >= 0 && c < BoardSize && board[r][c] == player {
			count++
			r -= dx
			c -= dy
		}

		if count >= 5 {
			return true
		}
	}

	return false
}

func cleanupEmptyRooms() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		roomsMu.Lock()
		for id, room := range rooms {
			if len(room.Players) == 0 && room.Status != "playing" {
				delete(rooms, id)
				delete(codeToRoom, room.Code)
				log.Printf("Cleaned up empty room: %s (code: %s)", id, room.Code)
			}
		}
		roomsMu.Unlock()
	}
}