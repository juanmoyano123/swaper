// Generado desde el esquema de Supabase (F-002). No editar a mano.
//
// Se regenera cuando cambia el esquema, con la herramienta `generate_typescript_types` del MCP de
// Supabase o con `supabase gen types typescript`. Si este archivo y la base se contradicen, manda
// la base: el esquema vive en supabase/migrations/ y está documentado en docs/esquema-datos.md.

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.15"
  }
  public: {
    Tables: {
      carteras: {
        Row: {
          actualizado_en: string
          creado_en: string
          descripcion: string | null
          id: string
          nombre: string
          user_id: string
        }
        Insert: {
          actualizado_en?: string
          creado_en?: string
          descripcion?: string | null
          id?: string
          nombre: string
          user_id: string
        }
        Update: {
          actualizado_en?: string
          creado_en?: string
          descripcion?: string | null
          id?: string
          nombre?: string
          user_id?: string
        }
        Relationships: []
      }
      cashflow: {
        Row: {
          capital: number | null
          cash_flow: number | null
          interest_amount: number | null
          interest_rate: number | null
          issue_date: string | null
          payment_date: string
          residual_value: number | null
          ticker: string
          type: string
        }
        Insert: {
          capital?: number | null
          cash_flow?: number | null
          interest_amount?: number | null
          interest_rate?: number | null
          issue_date?: string | null
          payment_date: string
          residual_value?: number | null
          ticker: string
          type: string
        }
        Update: {
          capital?: number | null
          cash_flow?: number | null
          interest_amount?: number | null
          interest_rate?: number | null
          issue_date?: string | null
          payment_date?: string
          residual_value?: number | null
          ticker?: string
          type?: string
        }
        Relationships: []
      }
      condiciones_emision: {
        Row: {
          actualizado_en: string
          calificacion: string | null
          calificacion_fecha: string | null
          calificacion_origen: string | null
          lamina: number | null
          lamina_fecha: string | null
          lamina_origen: string | null
          ley: string | null
          ley_fecha: string | null
          ley_origen: string | null
          moneda_pago: string | null
          moneda_pago_fecha: string | null
          moneda_pago_origen: string | null
          sector: string | null
          sector_fecha: string | null
          sector_origen: string | null
          ticker: string
          underlying: string | null
          underlying_fecha: string | null
          underlying_origen: string | null
        }
        Insert: {
          actualizado_en?: string
          calificacion?: string | null
          calificacion_fecha?: string | null
          calificacion_origen?: string | null
          lamina?: number | null
          lamina_fecha?: string | null
          lamina_origen?: string | null
          ley?: string | null
          ley_fecha?: string | null
          ley_origen?: string | null
          moneda_pago?: string | null
          moneda_pago_fecha?: string | null
          moneda_pago_origen?: string | null
          sector?: string | null
          sector_fecha?: string | null
          sector_origen?: string | null
          ticker: string
          underlying?: string | null
          underlying_fecha?: string | null
          underlying_origen?: string | null
        }
        Update: {
          actualizado_en?: string
          calificacion?: string | null
          calificacion_fecha?: string | null
          calificacion_origen?: string | null
          lamina?: number | null
          lamina_fecha?: string | null
          lamina_origen?: string | null
          ley?: string | null
          ley_fecha?: string | null
          ley_origen?: string | null
          moneda_pago?: string | null
          moneda_pago_fecha?: string | null
          moneda_pago_origen?: string | null
          sector?: string | null
          sector_fecha?: string | null
          sector_origen?: string | null
          ticker?: string
          underlying?: string | null
          underlying_fecha?: string | null
          underlying_origen?: string | null
        }
        Relationships: []
      }
      instrumentos: {
        Row: {
          actualizado_en: string
          archivo_origen: string | null
          calificacion: string | null
          clase_activo: string
          coupon_currency: string | null
          duplicado: boolean
          lamina: number | null
          law: string | null
          maturity: string | null
          revisar: boolean
          sector: string | null
          subtipo: string | null
          ticker: string
          tipo_tasa: string | null
          underlying: string | null
        }
        Insert: {
          actualizado_en?: string
          archivo_origen?: string | null
          calificacion?: string | null
          clase_activo: string
          coupon_currency?: string | null
          duplicado?: boolean
          lamina?: number | null
          law?: string | null
          maturity?: string | null
          revisar?: boolean
          sector?: string | null
          subtipo?: string | null
          ticker: string
          tipo_tasa?: string | null
          underlying?: string | null
        }
        Update: {
          actualizado_en?: string
          archivo_origen?: string | null
          calificacion?: string | null
          clase_activo?: string
          coupon_currency?: string | null
          duplicado?: boolean
          lamina?: number | null
          law?: string | null
          maturity?: string | null
          revisar?: boolean
          sector?: string | null
          subtipo?: string | null
          ticker?: string
          tipo_tasa?: string | null
          underlying?: string | null
        }
        Relationships: []
      }
      posiciones: {
        Row: {
          cantidad: number
          cartera_id: string
          creado_en: string
          fecha_compra: string | null
          id: string
          precio_compra: number | null
          ticker: string
          user_id: string
        }
        Insert: {
          cantidad: number
          cartera_id: string
          creado_en?: string
          fecha_compra?: string | null
          id?: string
          precio_compra?: number | null
          ticker: string
          user_id: string
        }
        Update: {
          cantidad?: number
          cartera_id?: string
          creado_en?: string
          fecha_compra?: string | null
          id?: string
          precio_compra?: number | null
          ticker?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "posiciones_cartera_id_fkey"
            columns: ["cartera_id"]
            isOneToOne: false
            referencedRelation: "carteras"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "posiciones_ticker_fkey"
            columns: ["ticker"]
            isOneToOne: false
            referencedRelation: "instrumentos"
            referencedColumns: ["ticker"]
          },
          {
            foreignKeyName: "posiciones_ticker_fkey"
            columns: ["ticker"]
            isOneToOne: false
            referencedRelation: "resumen"
            referencedColumns: ["ticker"]
          },
        ]
      }
      precios: {
        Row: {
          capturado_en: string
          duration: number | null
          effective_volume: number | null
          fuente: string | null
          last_price: number | null
          paridad: number | null
          residual_value: number | null
          ticker: string
          tir: number | null
          tna: number | null
        }
        Insert: {
          capturado_en: string
          duration?: number | null
          effective_volume?: number | null
          fuente?: string | null
          last_price?: number | null
          paridad?: number | null
          residual_value?: number | null
          ticker: string
          tir?: number | null
          tna?: number | null
        }
        Update: {
          capturado_en?: string
          duration?: number | null
          effective_volume?: number | null
          fuente?: string | null
          last_price?: number | null
          paridad?: number | null
          residual_value?: number | null
          ticker?: string
          tir?: number | null
          tna?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "precios_ticker_fkey"
            columns: ["ticker"]
            isOneToOne: false
            referencedRelation: "instrumentos"
            referencedColumns: ["ticker"]
          },
          {
            foreignKeyName: "precios_ticker_fkey"
            columns: ["ticker"]
            isOneToOne: false
            referencedRelation: "resumen"
            referencedColumns: ["ticker"]
          },
        ]
      }
      propuestas: {
        Row: {
          cartera_id: string | null
          creado_en: string
          estado: string
          id: string
          payload: Json
          user_id: string
        }
        Insert: {
          cartera_id?: string | null
          creado_en?: string
          estado?: string
          id?: string
          payload?: Json
          user_id: string
        }
        Update: {
          cartera_id?: string | null
          creado_en?: string
          estado?: string
          id?: string
          payload?: Json
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "propuestas_cartera_id_fkey"
            columns: ["cartera_id"]
            isOneToOne: false
            referencedRelation: "carteras"
            referencedColumns: ["id"]
          },
        ]
      }
      puntas: {
        Row: {
          capturado_en: string
          fuente: string | null
          operaciones: number | null
          px_ask: number | null
          px_bid: number | null
          ticker: string
        }
        Insert: {
          capturado_en: string
          fuente?: string | null
          operaciones?: number | null
          px_ask?: number | null
          px_bid?: number | null
          ticker: string
        }
        Update: {
          capturado_en?: string
          fuente?: string | null
          operaciones?: number | null
          px_ask?: number | null
          px_bid?: number | null
          ticker?: string
        }
        Relationships: []
      }
    }
    Views: {
      resumen: {
        Row: {
          archivo_origen: string | null
          calificacion: string | null
          clase_activo: string | null
          couponCurrency: string | null
          duplicado: boolean | null
          duration: number | null
          effectiveVolume: number | null
          lamina: number | null
          lastPrice: number | null
          law: string | null
          maturity: string | null
          paridad: number | null
          residualValue: number | null
          revisar: boolean | null
          sector: string | null
          subtipo: string | null
          ticker: string | null
          tipo_tasa: string | null
          tir: number | null
          tna: number | null
          underlying: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
